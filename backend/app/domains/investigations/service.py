"""Investigations: create (AC1-gated), run the S2 pipeline prefix, serialize."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ...errors import AppError
from ...models.detection import DetectionResult, MaterialityScore
from ...models.investigation import Investigation
from ...models.kpi import Kpi
from ...models.reconciliation import ReconciliationRun
from ...services import telemetry
from ...services.audit import record as audit
from ...services.pipeline import events
from ...services.pipeline.runner import RunContext, Stage, run_stages
from ..contracts.service import assert_contract_ready, gap_report
from ..detect import service as detect_service
from ..explain import decomposition as explain_decomposition
from ...services.entitlements import mask_columns
from ..decisions import service as decisions_service
from ..explain import certainty as explain_certainty
from ..explain import hypotheses as explain_hypotheses
from ..reconcile import service as reconcile_service


def _active_investigation(db: Session, organization_id: str, kpi_id: str) -> Investigation | None:
    return (
        db.query(Investigation)
        .filter(
            Investigation.organization_id == organization_id,
            Investigation.kpi_id == kpi_id,
            Investigation.workflow_state.notin_(("FAILED", "LEARNED", "ABSTAINED")),
        )
        .first()
    )


def create_investigation(
    db: Session, organization_id: str, kpi_id: str, actor_user_id: str, actor_role: str
) -> Investigation:
    kpi = db.query(Kpi).filter(Kpi.organization_id == organization_id, Kpi.id == kpi_id).first()
    if kpi is None:
        raise AppError("NOT_FOUND", "KPI not found", 404)
    contract = assert_contract_ready(db, organization_id, kpi_id)  # AC1 gate — governance first
    existing = _active_investigation(db, organization_id, kpi_id)
    if existing is not None:
        raise AppError(
            "INVESTIGATION_EXISTS",
            f"An active investigation already exists for {kpi.code} (state {existing.workflow_state})",
            409,
            details={"investigation_id": existing.id},
        )

    investigation = Investigation(
        organization_id=organization_id,
        kpi_id=kpi_id,
        contract_id=contract.id,
        contract_version=contract.version,  # pinned for reproducibility
        workflow_state="CONTRACT_READY",
        created_by_user_id=actor_user_id,
    )
    db.add(investigation)
    db.flush()

    run_id = f"inv-{investigation.id[:12]}"
    ctx = RunContext(db=db, investigation=investigation, organization_id=organization_id, run_id=run_id)

    def stage_contract_assert(c: RunContext):
        gaps = gap_report(c.db, contract)
        c.investigation.summary = {"contract_gaps": [g["code"] for g in gaps]}
        c.investigation.period_key = _latest_period(c)
        c.db.add(c.investigation)
        return contract

    def stage_reconcile(c: RunContext) -> ReconciliationRun:
        run = reconcile_service.run_reconciliation(
            c.db, contract, c.investigation.period_key or "P14",
            actor_user_id=actor_user_id, run_id=c.run_id, investigation_id=c.investigation.id,
        )
        c.investigation.reliability_snapshot = run.reliability_score
        c.investigation.confidence_cap_snapshot = run.confidence_cap
        c.investigation.working_value_snapshot = run.working_value
        c.db.add(c.investigation)
        return run

    detection_holder: dict = {}

    def stage_detect(c: RunContext) -> DetectionResult:
        detection = detect_service.run_detect(c.db, contract, run_id=c.run_id)
        c.investigation.cold_start_mode = detection.cold_start_flag
        c.db.add(c.investigation)
        detection_holder["detection"] = detection
        return detection

    def stage_triage(c: RunContext) -> MaterialityScore:
        score = detect_service.run_triage(c.db, contract, detection_holder["detection"], run_id=c.run_id)
        detection_holder["materiality"] = score
        return score

    def stage_decompose(c: RunContext):
        return explain_decomposition.decompose(
            c.db, c.organization_id, c.investigation, detection_holder["detection"]
        )

    hyp_holder: dict = {}

    def stage_hypothesize(c: RunContext):
        hyps = explain_hypotheses.hypothesize(c.db, c.organization_id, c.investigation, contract)
        hyp_holder["hypotheses"] = hyps
        return hyps[0] if hyps else None

    def stage_gather(c: RunContext):
        return explain_hypotheses.gather_evidence(
            c.db, c.organization_id, c.investigation, hyp_holder["hypotheses"],
            retriever_role=actor_role,
        )

    def stage_score(c: RunContext):
        cap = float(c.investigation.confidence_cap_snapshot or 1.0)
        ranked = explain_hypotheses.score_and_rank(
            c.db, c.organization_id, c.investigation, hyp_holder["hypotheses"], cap
        )
        lead = ranked[0] if ranked else None
        c.investigation.summary = {
            **(c.investigation.summary or {}),
            "lead_hypothesis": lead.code if lead else None,
            "lead_confidence": lead.final_confidence if lead else None,
            "runner_up_confidence": ranked[1].confidence if len(ranked) > 1 else None,
            "detection_baseline": float(detection_holder["detection"].baseline),
        }
        c.db.add(c.investigation)
        return lead

    def stage_certainty(c: RunContext):
        ranked = hyp_holder["hypotheses"] or []
        ranked = sorted(ranked, key=lambda h: h.rank or 99)
        return explain_certainty.assess_certainty(
            c.db, c.organization_id, c.investigation, ranked,
            detection_holder["detection"], detection_holder.get("materiality"),
        )

    stages = [
        Stage("contract_assert", "rules", None,
              "contract_ready", "Contract verified — governance before reasoning", stage_contract_assert),
        Stage("reconcile", "rules", ("CONTRACT_READY", "RECONCILING"),
              "reconcile_start", "Reconciling sources…", lambda c: None),
        Stage("reconcile", "rules", ("RECONCILING", "RECONCILED"),
              "reconciliation_complete", "Reconciliation complete", stage_reconcile),
        Stage("detect", "stats", ("RECONCILED", "DETECTING"),
              "detect_start", "Detecting movement…", lambda c: None),
        Stage("detect", "stats", ("DETECTING", "DETECTED"),
              "detection_complete", "Detection complete", stage_detect),
        Stage("triage", "rules", ("DETECTED", "TRIAGED"),
              "triage_complete", "Materiality assessed", stage_triage),
        Stage("decompose", "sql", ("TRIAGED", "EXPLAINING"),
              "decompose_start", "Decomposing the movement…", lambda c: None),
        Stage("decompose", "sql", None,
              "decomposition_complete", "Decomposition complete — components reconcile to the movement", stage_decompose),
        Stage("hypothesize", "rules", None,
              "hypotheses_generated", "Competing hypotheses drafted from contract drivers", stage_hypothesize),
        Stage("gather", "retrieval", None,
              "evidence_retrieved", "Evidence retrieved — scoped to case and entitlements", stage_gather),
        Stage("score_rank", "stats", ("EXPLAINING", "EXPLAINED"),
              "ranking_complete", "Hypotheses scored and ranked — deterministic", stage_score),
        Stage("certainty", "rules", ("EXPLAINED", "CERTAINTY_DECISION"),
              "certainty_state_determined", "Certainty state determined — backend rules, LLM has no vote", stage_certainty),
    ]

    audit(db, organization_id, "investigation.create", "investigation", investigation.id,
          actor_user_id, actor_role, details={"kpi": kpi.code, "contract_version": contract.version})
    events.emit(run_id, "investigation_started", f"Investigation opened for {kpi.name}")
    run_stages(ctx, stages)

    # Certainty terminal branch (S5): ABSTAIN / CLARIFY terminate here; ACT states
    # wait for the decision branch (S7+). Determined by backend rules, never a persona.
    if ctx.investigation.workflow_state == "CERTAINTY_DECISION":
        terminal_stage = {
            "ABSTAIN": Stage("certainty_abstain", "rules", ("CERTAINTY_DECISION", "ABSTAINED"),
                             "investigation_abstained", "ABSTAINED — no action options will be offered; six fields recorded", lambda c: c.investigation.abstention),
            "CLARIFY": Stage("certainty_clarify", "rules", ("CERTAINTY_DECISION", "CLARIFY"),
                             "investigation_awaiting_clarification", "CLARIFY — named gap routed to owner; auto-resumes when data arrives", lambda c: c.investigation.clarification),
        }.get(ctx.investigation.certainty_state or "")
        if terminal_stage is not None:
            run_stages(ctx, [terminal_stage])
        elif ctx.investigation.certainty_state in ("ACT", "ACT_WITH_CAUTION"):
            # Decision branch: options from ACTIVE scenario config (AC18), then
            # simulate → guardrails → rights. Human approval happens separately.
            def stage_options(c: RunContext):
                opts = decisions_service.generate_options(c.db, c.organization_id, c.investigation)
                return opts[0] if opts else None

            def stage_second_order(c: RunContext):
                from ..decisions.secondorder import annotate_options
                opts = decisions_service.options_for_investigation(c.db, c.organization_id, c.investigation.id)
                annotate_options(c.db, c.organization_id, c.investigation, opts)
                return opts[0] if opts else None

            def stage_collisions(c: RunContext):
                from ..decisions.collisions import detect_collisions
                opts = decisions_service.options_for_investigation(c.db, c.organization_id, c.investigation.id)
                # deterministic re-runs rewrite collisions
                from ...models.decisions import DecisionCollision
                c.db.query(DecisionCollision).filter(
                    DecisionCollision.organization_id == c.organization_id,
                    DecisionCollision.investigation_id == c.investigation.id,
                ).delete(synchronize_session=False)
                c.db.flush()
                rows = detect_collisions(c.db, c.organization_id, c.investigation, opts)
                high = next((r for r in rows if r.severity == "HIGH" and not r.resolved), None)
                if high is not None:
                    events.emit(c.run_id, "decision_collision_detected",
                                f"HIGH collision: {' + '.join(high.option_codes)} on {high.affected_kpi} "
                                f"(combined {high.combined_effect_pct:+.0%}) — approval blocked until resolved")
                return high

            run_stages(ctx, [
                Stage("generate_options", "rules", ("CERTAINTY_DECISION", "DECISION_OPTIONS_GENERATED"),
                      "options_generated", "Decision options generated from scenario configuration", stage_options),
                Stage("simulate", "stats", ("DECISION_OPTIONS_GENERATED", "SIMULATED"),
                      "options_simulated", "Options simulated — deterministic arithmetic",
                      lambda c: decisions_service.simulate_options(c.db, c.organization_id, c.investigation)[0]),
                Stage("guardrails", "rules", ("SIMULATED", "GUARDRAILS_CHECKED"),
                      "guardrails_checked", "Guardrails checked — hard FAIL blocks approval",
                      lambda c: decisions_service.guardrail_options(c.db, c.organization_id, c.investigation)[0]),
                Stage("second_order", "graph_elasticity", ("GUARDRAILS_CHECKED", "SECOND_ORDER_ANALYZED"),
                      "second_order_complete", "Second-order impacts propagated over kpi_relations + impact edges", stage_second_order),
                Stage("collisions", "rules", ("SECOND_ORDER_ANALYZED", "COLLISIONS_CHECKED"),
                      "collision_check_complete", "Decision collisions checked — unresolved HIGH blocks approval", stage_collisions),
                Stage("rights", "rules", ("COLLISIONS_CHECKED", "RIGHTS_CHECKED"),
                      "rights_checked", "Rights verdicts applied from the contract",
                      lambda c: decisions_service.rights_options(c.db, c.organization_id, c.investigation)[0]),
            ])
    events.emit(
        run_id, "prefix_complete",
        {
            "TRIAGED": "Reconcile → Detect → Triage complete",
            "EXPLAINING": "Reconcile → Detect → Triage → Decompose complete",
            "EXPLAINED": "Explain complete — decomposition, hypotheses, evidence, ranking",
            "CERTAINTY_DECISION": "Certainty determined — ready for the decision branch",
            "ABSTAINED": "ABSTAINED — the platform refuses to recommend; six fields shown",
            "CLARIFY": "CLARIFY — named gap routed; investigation auto-resumes on data",
            "DECISION_OPTIONS_GENERATED": "Options generated — simulated, guardrailed, rights-checked",
            "SIMULATED": "Options simulated — deterministic",
            "GUARDRAILS_CHECKED": "Guardrails checked — hard FAIL blocks approval",
            "SECOND_ORDER_ANALYZED": "Second-order impacts surfaced (graph_elasticity)",
            "COLLISIONS_CHECKED": "Collisions checked — unresolved HIGH blocks approval",
            "RIGHTS_CHECKED": "Rights applied — approval now a human decision",
        }.get(ctx.investigation.workflow_state, f"Pipeline stopped: {ctx.investigation.workflow_state}"),
    )
    return investigation


def _latest_period(c: RunContext) -> str:
    from ...models.observation import KpiObservation

    row = (
        c.db.query(KpiObservation)
        .filter(
            KpiObservation.organization_id == c.organization_id,
            KpiObservation.kpi_id == c.investigation.kpi_id,
        )
        .order_by(KpiObservation.occurred_at.desc())
        .first()
    )
    return row.period_key if row else "P14"


def get_investigation(db: Session, organization_id: str, investigation_id: str) -> Investigation:
    inv = (
        db.query(Investigation)
        .filter(
            Investigation.organization_id == organization_id,
            Investigation.id == investigation_id,
        )
        .first()
    )
    if inv is None:
        raise AppError("NOT_FOUND", "Investigation not found", 404)
    return inv


def active_for_kpi(db: Session, organization_id: str, kpi_id: str) -> Investigation | None:
    return _active_investigation(db, organization_id, kpi_id)


def list_for_user(db: Session, organization_id: str, user, kpi_id: str | None = None, limit: int = 20):
    """Row-scoped listing (entitlements J.2): SUPPLY_CHAIN sees own-region KPIs only."""
    q = (
        db.query(Investigation)
        .filter(Investigation.organization_id == organization_id)
        .order_by(Investigation.created_at.desc())
    )
    if kpi_id:
        q = q.filter(Investigation.kpi_id == kpi_id)
    if user.role == "SUPPLY_CHAIN":
        scope = set(user.region_scope or [])
        if scope:
            q = q.join(Kpi, Kpi.id == Investigation.kpi_id).filter(Kpi.region.in_(scope))
    return q.limit(limit).all()


def serialize(db: Session, inv: Investigation, viewer_role: str | None = None) -> dict:
    kpi = inv.kpi
    latest_detection = detect_service.latest_detection(db, inv.organization_id, inv.kpi_id)
    latest_triage = detect_service.latest_materiality(db, inv.organization_id, inv.kpi_id)
    recon = (
        db.query(ReconciliationRun)
        .filter(ReconciliationRun.investigation_id == inv.id)
        .order_by(ReconciliationRun.run_ts.desc())
        .first()
    )
    return {
        "id": inv.id,
        "kpi": {"id": kpi.id, "code": kpi.code, "name": kpi.name, "unit": kpi.unit, "region": kpi.region} if kpi else None,
        "contract_id": inv.contract_id,
        "contract_version": inv.contract_version,
        "workflow_state": inv.workflow_state,
        "period_key": inv.period_key,
        "reliability": inv.reliability_snapshot,
        "confidence_cap": inv.confidence_cap_snapshot,
        "working_value": inv.working_value_snapshot,
        "cold_start_mode": inv.cold_start_mode,
        "summary": inv.summary,
        "last_error": inv.last_error or None,
        "detection": _serialize_detection(latest_detection),
        "materiality": _serialize_triage(latest_triage),
        "reconciliation_run_id": recon.id if recon else None,
        "options": _serialize_options(db, inv),
        "collisions": _serialize_collisions(db, inv),
        "certainty_state": inv.certainty_state,
        "final_confidence": inv.final_confidence,
        "lead_margin": inv.lead_margin,
        "certainty_reasons": inv.certainty_reasons or [],
        "abstention": inv.abstention or None,
        "clarification": inv.clarification or None,
        "hypotheses": _serialize_hypotheses(db, inv, viewer_role=viewer_role),
        "stage_events": [
            {
                "from_state": e.from_state, "to_state": e.to_state,
                "stage_code": e.stage_code, "ok": e.ok, "message": e.message,
            }
            for e in inv.stage_events
        ],
        "telemetry": telemetry.summarize(telemetry.rows_for_run(db, inv.organization_id, f"inv-{inv.id[:12]}")),
    }


def _serialize_collisions(db: Session, inv: Investigation) -> list[dict]:
    from ..decisions.collisions import serialize_collision
    from ...models.decisions import DecisionCollision
    rows = (
        db.query(DecisionCollision)
        .filter(DecisionCollision.organization_id == inv.organization_id,
                DecisionCollision.investigation_id == inv.id)
        .order_by(DecisionCollision.created_at.asc())
        .all()
    )
    return [serialize_collision(r) for r in rows]


def _serialize_options(db: Session, inv: Investigation) -> list[dict]:
    from ...models.decisions import DecisionRecord
    from ..decisions import service as ds
    opts = ds.options_for_investigation(db, inv.organization_id, inv.id)
    out = []
    for o in opts:
        rec = (
            db.query(DecisionRecord)
            .filter(DecisionRecord.option_id == o.id)
            .order_by(DecisionRecord.created_at.desc())
            .first()
        )
        out.append(ds.serialize(o, rec))
    return out


def _serialize_hypotheses(db: Session, inv: Investigation, viewer_role: str | None = None) -> list[dict]:
    """Hypotheses + evidence links. When viewer_role is set, documents the viewer
    cannot open keep their identity/state but lose content: counted honestly as
    withheld, never silently omitted (AC7/AC9)."""
    from ...models.evidence import EvidenceRecord, HypothesisEvidence
    from ...services.entitlements import can_access_doc
    from ..explain import hypotheses as hh

    def can_open(doc: EvidenceRecord | None) -> bool:
        return doc is None or viewer_role is None or can_access_doc(doc, viewer_role)

    from ...services.entitlements import audit_masking
    rows = hh.for_investigation(db, inv.organization_id, inv.id)
    out = []
    masked_any: list[str] = []
    for h in rows:
        d = hh.serialize(h)
        links = (
            db.query(HypothesisEvidence)
            .filter(HypothesisEvidence.hypothesis_id == h.id)
            .all()
        )
        evidence_out = []
        for l in links:
            doc = l.evidence
            visible = can_open(doc)
            if visible and viewer_role:
                claims_out, hits = mask_columns(doc.claims, viewer_role)
                masked_any.extend(hits)
            else:
                claims_out = doc.claims if visible else []
            if doc is None:
                evidence_out.append({"doc_key": None, "title": None, "state": l.state, "weight": l.weight,
                                     "source": None, "data_classification": None, "freshness": None,
                                     "lineage": None, "summary": None, "access_roles": [], "claims": [],
                                     "withheld": False})
                continue
            evidence_out.append({
                "doc_key": doc.doc_key,
                "title": doc.title if visible else "— source withheld for your role —",
                "state": l.state,
                "weight": l.weight if visible else 0.0,
                "source": doc.source.code if doc.source else None,
                "data_classification": doc.data_classification,
                "freshness": doc.freshness_score if visible else None,
                "lineage": doc.lineage if visible else None,
                "summary": doc.summary if visible else None,
                "access_roles": doc.access_roles,
                "claims": claims_out if visible else [],
                "withheld": not visible,
            })
        d["evidence"] = evidence_out
        out.append(d)
    if viewer_role and masked_any:
        audit_masking(db, inv.organization_id, inv.created_by_user_id or "", masked_any, f"investigation:{inv.id}:{viewer_role}")
    return out


def _serialize_detection(d: DetectionResult | None) -> dict | None:
    if d is None:
        return None
    return {
        "period_key": d.period_key, "source_value": d.source_value, "baseline": d.baseline,
        "ci_lo": d.ci_lo, "ci_hi": d.ci_hi, "deviation": d.deviation, "deviation_pct": d.deviation_pct,
        "robust_z": d.robust_z, "anomaly_score": d.anomaly_score,
        "statistical_significance": d.statistical_significance, "history_n": d.history_n,
        "cold_start_flag": d.cold_start_flag, "method": d.method, "model_version": d.model_version,
    }


def _serialize_triage(m: MaterialityScore | None) -> dict | None:
    if m is None:
        return None
    return {
        "band": m.band, "score": m.score, "significance": m.significance,
        "exposure_rs": m.exposure_rs, "arithmetic": m.arithmetic,
        "monitor_only": m.monitor_only, "period_key": m.period_key,
    }
