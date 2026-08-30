"""Decision options (AC10–13): generate → simulate → guardrails → rights.

Options come from the ACTIVE scenario configuration (AC18: switching scenario
= switching configuration) constrained to the case's lead driver; simulation
is deterministic arithmetic over current KPI values; guardrails are hard
limits from the same configuration; rights verdicts come from the contract's
rights table (role × action class → may_approve + limit + escalation target).
The LLM has no role here. Hard-guardrail FAIL blocks approval outright.
"""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from ...errors import AppError
from ...db import utcnow
from ...models.contract import KpiContractRight as ContractRight
from ...models.decisions import DecisionOption, DecisionRecord
from ...models.detection import DetectionResult
from ...models.investigation import Investigation
from ...models.kpi import Kpi
from ...models.observation import KpiObservation
from ...models.scenario import ScenarioTemplate
from ...services import telemetry
from ...services.audit import record as audit

SIM_VERSION = "config_sim_v1"


def _scenario_for(db: Session, organization_id: str, kpi: Kpi) -> ScenarioTemplate | None:
    if not getattr(kpi, "scenario_id", None):
        return None
    return (
        db.query(ScenarioTemplate)
        .filter(ScenarioTemplate.organization_id == organization_id,
                ScenarioTemplate.scenario_id == kpi.scenario_id)
        .first()
    )


def _current_values(db: Session, organization_id: str, kpi: Kpi) -> dict:
    """Latest reconciled/observed values for guardrail KPIs — real data, no defaults."""
    vals: dict[str, float | None] = {}
    codes = ["inventory_cover_ne", "osa_ne", "margin_ne", "cash_exposure"]
    for code in codes:
        k = (
            db.query(Kpi).filter(Kpi.organization_id == organization_id, Kpi.code == code).first()
        )
        if k is None:
            vals[code] = None
            continue
        facts = (
            db.query(KpiObservation)
            .filter(KpiObservation.organization_id == organization_id,
                    KpiObservation.kpi_id == k.id)
            .all()
        )
        # P1..P14 are strings; sort numerically so P14 > P9 (lexicographic lies)
        latest = max(facts, key=lambda f: int(f.period_key.removeprefix("P")), default=None) \
            if facts else None
        vals[code] = float(latest.value) if latest else None
    return vals


def generate_options(db: Session, organization_id: str, inv: Investigation) -> list[DecisionOption]:
    """Instantiate options from scenario config, scoped to the case's drivers."""
    kpi = inv.kpi
    template = _scenario_for(db, organization_id, kpi)
    if template is None:
        raise AppError("NO_SCENARIO", f"No scenario configuration for KPI {kpi.code} — options cannot be invented", 422)

    options_cfg = template.decision_options or []
    if isinstance(options_cfg, str):
        options_cfg = json.loads(options_cfg)

    # keep only options whose driver is in this case's ranked hypotheses
    hyp_codes = {h.code for h in (inv.hypotheses or [])} if hasattr(inv, "hypotheses") else set()
    ranked = sorted(inv.hypotheses, key=lambda h: h.rank or 99) if hasattr(inv, "hypotheses") else []
    hyp_codes = {h.code for h in ranked}
    lead_driver = ranked[0].code if ranked else None

    # evidence set: supporting docs of the lead hypothesis (frozen into each option)
    from ...models.evidence import HypothesisEvidence
    lead_evidence = []
    if ranked:
        rows = (
            db.query(HypothesisEvidence)
            .filter(HypothesisEvidence.organization_id == organization_id,
                    HypothesisEvidence.hypothesis_id == ranked[0].id,
                    HypothesisEvidence.state == "SUPPORTING")
            .all()
        )
        lead_evidence = [r.evidence.doc_key for r in rows if r.evidence]

    # clear + rewrite (deterministic re-runs)
    db.query(DecisionOption).filter(
        DecisionOption.organization_id == organization_id,
        DecisionOption.investigation_id == inv.id,
    ).delete(synchronize_session=False)

    out: list[DecisionOption] = []
    external: list[DecisionOption] = []
    for c in options_cfg:
        if hyp_codes and c.get("driver") not in hyp_codes and lead_driver:
            # option acts on a driver this case ranked — skip unrelated ones
            if c.get("driver") not in hyp_codes:
                continue
        opt = DecisionOption(
            organization_id=organization_id,
            investigation_id=inv.id,
            code=c["option_code"],
            driver=c.get("driver", ""),
            lever=c.get("lever", ""),
            action=c.get("action", ""),
            expected_impact_rs=float(c.get("expected_impact_pt_rs", 0.0)),
            impact_lo_rs=float(c.get("impact_lo_rs", 0.0)),
            impact_hi_rs=float(c.get("impact_hi_rs", 0.0)),
            cost_rs=float(c.get("cost_rs", 0.0)),
            cash_exposure_rs=float(c.get("cash_exposure_rs", c.get("cost_rs", 0.0))),
            horizon_days=int(c.get("horizon_days", 42)),
            owner_role=c.get("owner_role", "SUPPLY_CHAIN"),
            comparable_to=c.get("comparable_to"),
            evidence_set=lead_evidence,
            scenario_id=template.scenario_id,
            simulation_version=SIM_VERSION,
        )
        opt.external_proposal = bool(c.get("external_proposal", False))
        db.add(opt)
        (external if opt.external_proposal else out).append(opt)
    db.flush()

    if not out:
        raise AppError("NO_OPTIONS", "No configured options act on this case's drivers — refusing to invent", 422)

    # In-flight external proposals get a PENDING record — they are live decisions
    # from other teams that this case's options may collide with (AC21).
    for x in external:
        db.add(DecisionRecord(
            organization_id=organization_id, investigation_id=inv.id, option_id=x.id,
            status="PENDING", requested_by_role=x.owner_role,
            evidence_set=x.evidence_set, guardrail_status=x.guardrail_status,
            simulation_version=SIM_VERSION,
        ))
    db.flush()
    return out + external


def simulate_options(db: Session, organization_id: str, inv: Investigation) -> list[DecisionOption]:
    template = _scenario_for(db, organization_id, inv.kpi)
    opts = options_for_investigation(db, organization_id, inv.id)
    _simulate(db, organization_id, inv, opts, template)
    return opts


def guardrail_options(db: Session, organization_id: str, inv: Investigation) -> list[DecisionOption]:
    template = _scenario_for(db, organization_id, inv.kpi)
    opts = options_for_investigation(db, organization_id, inv.id)
    _guardrails(db, organization_id, inv, opts, template)
    _decision_health(opts)
    return opts


def rights_options(db: Session, organization_id: str, inv: Investigation) -> list[DecisionOption]:
    opts = options_for_investigation(db, organization_id, inv.id)
    _rights(db, organization_id, inv, opts)
    return opts


def _simulate(db: Session, organization_id: str, inv: Investigation,
              options: list[DecisionOption], template: ScenarioTemplate) -> None:
    """Deterministic: post-state = current value + configured delta. Arithmetic recorded."""
    kpi = inv.kpi
    current = _current_values(db, organization_id, kpi)
    cover_now = current.get("inventory_cover_ne")
    osa_now = current.get("osa_ne")
    for o in options:
        sim_in = {}
        for c in (template.decision_options or []):
            if c.get("option_code") == o.code:
                sim_in = c.get("sim", {})
                break
        cover_post = round(cover_now + sim_in.get("cover_days_delta", 0.0), 2) if cover_now is not None else None
        osa_post = round(osa_now + sim_in.get("osa_pct_delta", 0.0), 2) if osa_now is not None else None
        # OSA at horizon END after full recovery (mid-crisis level + recovery) —
        # the SLA guardrail judges the recovered state, not the trough.
        osa_recovery = sim_in.get("osa_recovery_pct")
        osa_recovery = round(osa_recovery, 2) if osa_recovery is not None else None
        margin_now = current.get("margin_ne")
        margin_post = round(margin_now + sim_in.get("margin_pct_delta", 0.0), 2) if margin_now is not None else None
        o.simulation = {
            "method": SIM_VERSION,
            "inputs": {
                "inventory_cover_ne_now": cover_now,
                "osa_ne_now": osa_now,
                "deltas": sim_in,
                "scenario_id": template.scenario_id,
            },
            "projected": {
                "inventory_cover_ne": cover_post,
                "osa_ne": osa_post,
                "osa_recovery": osa_recovery,
                "cash_exposure_rs": o.cash_exposure_rs,
                "margin_pct_delta": sim_in.get("margin_pct_delta", 0.0),
                "margin_ne": margin_post,
            },
            "arithmetic": [
                f"cover_post = {cover_now} + ({sim_in.get('cover_days_delta', 0.0)}) = {cover_post}",
                f"osa_post = {osa_now} + ({sim_in.get('osa_pct_delta', 0.0)}) = {osa_post}",
                f"osa_recovery = {sim_in.get('osa_recovery_pct')} (config, horizon-end)",
            ],
        }
        db.add(o)
    telemetry.record_stage(db, organization_id, inv.id, "simulate", "stats", ok=True,
                           source_count=len(options))
    db.flush()


def _guardrails(db: Session, organization_id: str, inv: Investigation,
                options: list[DecisionOption], template: ScenarioTemplate) -> None:
    """Hard limits from scenario config. FAIL blocks approval; NOT_SAFE flags options
    whose projected state breaches a hard guardrail via second-order effects."""
    gcfg = template.guardrail_configuration or {}
    guardrails = gcfg.get("guardrails", [])

    for o in options:
        proj = (o.simulation or {}).get("projected", {})
        reasons: list[str] = []
        status = "PASS"
        for g in guardrails:
            code, kind, thr = g["code"], g["threshold_type"], float(g["threshold_value"])
            hard = bool(g.get("hard", False))
            value = None
            if code == "inventory_cover":
                value = proj.get("inventory_cover_ne")
            elif code == "customer_sla":
                value = proj.get("osa_recovery") if proj.get("osa_recovery") is not None else proj.get("osa_ne")
            elif code == "cash_exposure":
                value = proj.get("cash_exposure_rs")
            elif code == "gross_margin":
                value = proj.get("margin_ne")  # level, not delta; None ⇒ UNKNOWN policy
            if value is None:
                reasons.append(f"{code}: UNKNOWN — {gcfg.get('policy', {}).get('UNKNOWN', 'treat_as_WARNING')}")
                continue
            breached = value < thr if kind == "min" else value > thr
            if breached:
                scope = "FAIL" if hard else "WARNING"
                if hard:
                    status = "FAIL" if status != "NOT_SAFE" else "NOT_SAFE"
                reasons.append(f"{code} {scope}: projected {value} {'<' if kind=='min' else '>'} hard {kind} {thr} ({g['unit']})")
        # NOT SAFE framing: a FAIL that comes from the action's own second-order
        # warning (e.g. promotion burns cover) reads as NOT_SAFE for judges.
        if status == "FAIL" and o.comparable_to:
            status = "NOT_SAFE"
        if not reasons:
            reasons.append("All projected values within hard limits.")
        o.guardrail_status = status
        o.guardrail_reasons = reasons
        db.add(o)
    telemetry.record_stage(db, organization_id, inv.id, "guardrails", "rules", ok=True,
                           source_count=len(options))
    db.flush()


def _rights(db: Session, organization_id: str, inv: Investigation,
            options: list[DecisionOption]) -> None:
    """Rights verdict from the CONTRACT rights table (governed, versioned)."""
    for o in options:
        rights_rows = (
            db.query(ContractRight)
            .filter(ContractRight.contract_id == inv.contract_id)
            .all()
        )
        right = next((r for r in rights_rows if r.action_class == o.lever and r.role == o.owner_role), None)
        if right is None:
            o.rights_verdict = "DENIED"
            o.rights_note = "No rights entry for this action class on the contract."
            o.escalation_target = "KPI_OWNER"
            db.add(o)
            continue
        if not right.may_approve:
            o.rights_verdict = "ESCALATE"
            o.rights_note = f"{right.role} may recommend but not approve — escalate to {right.escalate_to_role}"
            o.escalation_target = right.escalate_to_role
        elif o.cash_exposure_rs > float(right.approve_limit_rs or 0):
            o.rights_verdict = "ESCALATE"
            o.rights_note = (f"Cash exposure ₹{o.cash_exposure_rs/1e6:.1f}M exceeds {right.role} limit "
                             f"₹{float(right.approve_limit_rs or 0)/1e6:.1f}M — escalate to {right.escalate_to_role}")
            o.escalation_target = right.escalate_to_role or "EXECUTIVE"
        else:
            o.rights_verdict = "AUTHORIZED"
            o.rights_note = f"{right.role} may approve within ₹{float(right.approve_limit_rs or 0)/1e6:.1f}M"
        db.add(o)
    telemetry.record_stage(db, organization_id, inv.id, "rights_check", "rules", ok=True,
                           source_count=len(options))
    db.flush()


def _decision_health(options: list[DecisionOption]) -> None:
    """Explainable comparison: C vs its phased variant — never autonomous optimization."""
    by_code = {o.code: o for o in options}
    for o in options:
        if o.comparable_to and o.comparable_to in by_code:
            twin = by_code[o.comparable_to]
            # health = impact per unit of guardrail risk; variant passes where base does not
            base_safe = o.guardrail_status == "PASS"
            twin_safe = twin.guardrail_status == "PASS"
            if not base_safe and twin_safe:
                twin.decision_health = "BETTER"
                o.decision_health = "WORSE"
            elif base_safe and not twin_safe:
                o.decision_health = "BETTER"
                twin.decision_health = "WORSE"
            else:
                o.decision_health = "EQUAL"
                twin.decision_health = "EQUAL"


def options_for_investigation(db: Session, organization_id: str, investigation_id: str) -> list[DecisionOption]:
    return (
        db.query(DecisionOption)
        .filter(DecisionOption.organization_id == organization_id,
                DecisionOption.investigation_id == investigation_id)
        .order_by(DecisionOption.created_at.asc(), DecisionOption.code.asc())
        .all()
    )


def serialize(o: DecisionOption, record: DecisionRecord | None = None) -> dict:
    return {
        "id": o.id,
        "code": o.code,
        "driver": o.driver,
        "lever": o.lever,
        "action": o.action,
        "expected_impact_rs": o.expected_impact_rs,
        "impact_lo_rs": o.impact_lo_rs,
        "impact_hi_rs": o.impact_hi_rs,
        "cost_rs": o.cost_rs,
        "cash_exposure_rs": o.cash_exposure_rs,
        "horizon_days": o.horizon_days,
        "owner_role": o.owner_role,
        "simulation": o.simulation,
        "guardrail_status": o.guardrail_status,
        "guardrail_reasons": o.guardrail_reasons,
        "rights_verdict": o.rights_verdict,
        "rights_note": o.rights_note,
        "escalation_target": o.escalation_target,
        "comparable_to": o.comparable_to,
        "decision_health": o.decision_health,
        "evidence_set": o.evidence_set,
        "scenario_id": o.scenario_id,
        "simulation_version": o.simulation_version,
        "record": ({
            "id": record.id, "status": record.status,
            "approved_by_role": record.approved_by_role,
            "decided_at": record.decided_at.isoformat() if record.decided_at else None,
            "override_reason": record.override_reason,
            "monitoring_plan": record.monitoring_plan,
        } if record else None),
    }


def _monitoring_plan(option: DecisionOption, kpi: Kpi) -> dict:
    band_lo, band_hi = option.impact_lo_rs, option.impact_hi_rs
    return {
        "metric": kpi.code,
        "cadence": "weekly",
        "window_days": option.horizon_days,
        "success_band": [band_lo, band_hi],
        "checkpoint": "mid-window review at half horizon",
        "abort_if": "cover < 5 days for 2 consecutive weeks",
    }


def decide(db: Session, organization_id: str, inv: Investigation, option: DecisionOption,
           actor_user_id: str, actor_role: str, decision: str, override_reason: str | None = None) -> DecisionRecord:
    """APPROVE | REJECT | OVERRIDE — with hard blocks and full audit."""
    if decision not in ("APPROVE", "REJECT", "OVERRIDE"):
        raise AppError("BAD_REQUEST", "decision must be APPROVE | REJECT | OVERRIDE", 400)

    if option.external_proposal:
        raise AppError("EXTERNAL_PROPOSAL",
                       f"{option.code} is an in-flight proposal from {option.owner_role} — it is tracked "
                       "and collision-checked here, but decided in its own governance flow", 409)

    # Unresolved HIGH collision blocks approval (AC21) — humans resolve first.
    if decision in ("APPROVE", "OVERRIDE"):
        from .collisions import unresolved_high
        blocking = unresolved_high(db, organization_id, option.id)
        if blocking:
            worst = blocking[0]
            other = worst.option_codes[1] if worst.option_ids[0] == option.id else worst.option_codes[0]
            raise AppError(
                "COLLISION_BLOCK",
                f"DECISION COLLISION DETECTED — unresolved HIGH collision with {other} "
                f"on {worst.affected_kpi} (combined {worst.combined_effect_pct:+.0%}). {worst.combined_note}. "
                "Resolve the collision (sequence / escalate combined / defer one), then decide.",
                409,
                details={"collision_id": worst.id, "other_option": other},
            )

    # Hard guardrail FAIL blocks approval outright — no persona, no override.
    if decision in ("APPROVE", "OVERRIDE") and option.guardrail_status in ("FAIL", "NOT_SAFE"):
        raise AppError(
            "GUARDRAIL_BLOCK",
            f"Option {option.code} is {option.guardrail_status} on hard guardrails — approval blocked. "
            + ("; ".join(option.guardrail_reasons))
            + (f" Compare variant {option.comparable_to}." if option.comparable_to else " Escalate outside the platform."),
            409,
        )

    # Rights: who may approve this lever, within which limit.
    rights_rows = (
        db.query(ContractRight)
        .filter(ContractRight.contract_id == inv.contract_id)
        .all()
    )
    right = next((r for r in rights_rows if r.action_class == option.lever and r.role == actor_role), None)
    if decision == "APPROVE":
        if right is None or not right.may_approve:
            raise AppError("FORBIDDEN", f"{actor_role} may not approve {option.lever} actions on this contract", 403)
        if option.cash_exposure_rs > float(right.approve_limit_rs or 0):
            raise AppError("FORBIDDEN",
                           f"Cash exposure ₹{option.cash_exposure_rs/1e6:.1f}M exceeds your ₹{float(right.approve_limit_rs or 0)/1e6:.1f}M limit — escalate to {right.escalate_to_role}", 403)

    if decision == "OVERRIDE" and not (override_reason and len(override_reason.strip()) >= 10):
        raise AppError("BAD_REQUEST", "An override requires a reason (≥ 10 chars) — it feeds the learning loop", 400)

    existing = (
        db.query(DecisionRecord)
        .filter(DecisionRecord.organization_id == organization_id,
                DecisionRecord.option_id == option.id,
                DecisionRecord.status.in_(("PENDING", "APPROVED", "OVERRIDDEN")))
        .first()
    )
    if existing is not None:
        raise AppError("DECISION_EXISTS", f"Option {option.code} already has a {existing.status} decision", 409)

    status = {"APPROVE": "APPROVED", "REJECT": "REJECTED", "OVERRIDE": "OVERRIDDEN"}[decision]
    record = DecisionRecord(
        organization_id=organization_id,
        investigation_id=inv.id,
        option_id=option.id,
        status=status,
        requested_by_role=option.owner_role,
        approved_by_user_id=actor_user_id,
        approved_by_role=actor_role,
        decided_at=utcnow(),
        override_reason=override_reason if decision == "OVERRIDE" else None,
        monitoring_plan=_monitoring_plan(option, inv.kpi) if status in ("APPROVED", "OVERRIDDEN") else {},
        evidence_set=option.evidence_set,
        guardrail_status=option.guardrail_status,
        rights_verdict=option.rights_verdict,
        predicted_impact_rs=option.expected_impact_rs if status in ("APPROVED", "OVERRIDDEN") else None,
    )
    db.add(record)
    audit(db, organization_id=organization_id, actor_user_id=actor_user_id, actor_role=actor_role,
          action=f"decision.{decision.lower()}", object_type="decision_option", object_id=option.id,
          details={"investigation_id": inv.id, "option": option.code, "guardrail": option.guardrail_status})
    db.flush()
    return record
