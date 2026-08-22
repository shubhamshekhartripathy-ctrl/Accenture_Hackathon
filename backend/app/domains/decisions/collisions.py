"""Decision collisions (AC21) — the platform surfaces, humans resolve.

A collision exists when two decisions affect the same KPI in the same units
with opposing signs, or amplify it beyond a guardrail threshold. Severity
HIGH/MEDIUM/LOW. **Unresolved HIGH collisions block approval.** Humans
resolve; the system never auto-optimizes.

Locked demo (every number deterministic and chain-derived):
    "Reduce procurement safety stock" (−15% inventory) +
    "Increase NE promotion"           (−18% inventory, via AC20 chain)
    ⇒ combined −33% cover  (effects add linearly on the shared KPI)
    ⇒ combined stockout risk +17 pts
       = |elasticity 0.667| × (18 + 0.5 × 15)   — damped second contributor
    ⇒ HIGH (combined cover 5.1d × 0.67 = 3.4d breaches the hard 5-day guardrail)

The 0.5 damping on the second contributor is the arch's "multiplicative
damping" applied to JOINT actions: the marginal damage of the second
inventory draw is lower than the first. It is documented here, in the
collision record, and in the tests.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ...errors import AppError
from ...models.contract import KpiContract, KpiRelation
from ...models.decisions import DecisionCollision, DecisionOption
from ...models.impacts import ImpactEdge
from ...models.investigation import Investigation
from ...models.kpi import Kpi
from ...models.observation import KpiObservation
from ...services import telemetry
from ...services.audit import record as audit

DAMPING_SECOND = 0.5  # damped marginal contribution of the second action (documented)

# hard guardrail floors used for HIGH-severity amplification (from scenario config)
_GUARDRAIL_MIN = {"inventory_cover_ne": 5.0}


def _effect_on(option: DecisionOption, kpi: str) -> float | None:
    sim = option.simulation or {}
    direct = (sim.get("inputs", {}).get("deltas", {}) or {}).get("direct_pct", {})
    if kpi in direct:
        return float(direct[kpi])
    for row in (sim.get("second_order") or {}).get("effects", []):
        if row["kpi"] == kpi:
            return float(row["effect_pct"])
    return None


def _shared_kpis(db: Session, organization_id: str, a: DecisionOption, b: DecisionOption) -> set[str]:
    """Shared PRIMARY KPI surfaces (units well-defined, guardrails live here).
    Derived impact metrics are downstream consequences — they enter through the
    damped combined_note, never as separate collision rows (their linear sum
    would contradict the damped joint model)."""
    primary = {k.code for k in db.query(Kpi).filter(Kpi.organization_id == organization_id).all()}

    def surfaces(o: DecisionOption) -> set[str]:
        sim = o.simulation or {}
        out = set((sim.get("inputs", {}).get("deltas", {}) or {}).get("direct_pct", {}))
        out |= {r["kpi"] for r in (sim.get("second_order") or {}).get("effects", [])
                if r.get("node_kind") == "KPI"}
        return out & primary
    return surfaces(a) & surfaces(b)


def _current_level(db: Session, organization_id: str, kpi_code: str) -> float | None:
    k = db.query(Kpi).filter(Kpi.organization_id == organization_id, Kpi.code == kpi_code).first()
    if k is None:
        return None
    facts = db.query(KpiObservation).filter(
        KpiObservation.organization_id == organization_id, KpiObservation.kpi_id == k.id
    ).all()
    if not facts:
        return None
    latest = max(facts, key=lambda f: int(f.period_key.removeprefix("P")))  # P14 > P9 numerically
    return float(latest.value)


def _downstream_note(db: Session, organization_id: str, kpi: str,
                     ea: float, eb: float) -> str:
    """Locked joint downstream effect: |elasticity| × (|larger| + 0.5×|smaller|)."""
    edge = (
        db.query(ImpactEdge)
        .filter(ImpactEdge.organization_id == organization_id, ImpactEdge.parent_code == kpi)
        .first()
    )
    if edge is None:
        # fall back to a kpi_relations edge (percentage semantics)
        codes = {
            c.id: (c.kpi.code if c.kpi else None)
            for c in db.query(KpiContract).filter(KpiContract.organization_id == organization_id).all()
        }
        for rel in db.query(KpiRelation).filter(KpiRelation.organization_id == organization_id).all():
            if codes.get(rel.a_contract_id) == kpi:
                edge = rel
                break
    if edge is None:
        return ""
    elasticity = float(edge.elasticity)
    child_code = edge.child_code if hasattr(edge, "child_code") else _code_of(db, organization_id, edge.b_contract_id)
    if not child_code:
        return ""
    larger, smaller = max(abs(ea), abs(eb)), min(abs(ea), abs(eb))  # natural display units
    downstream = abs(elasticity) * (larger + DAMPING_SECOND * smaller)
    return (f"combined {kpi} {ea + eb:+.0f}% → {child_code} ≈ +{downstream:.0f} pts "
            f"(|{elasticity}| × ({larger:.0f} + {DAMPING_SECOND} × {smaller:.0f}))")


def _code_of(db: Session, organization_id: str, contract_id: str) -> str | None:
    c = db.query(KpiContract).filter(KpiContract.id == contract_id).first()
    return c.kpi.code if c and c.kpi else None


def detect_collisions(db: Session, organization_id: str, inv: Investigation,
                      options: list[DecisionOption]) -> list[DecisionCollision]:
    candidates = list(options)
    rows: list[DecisionCollision] = []
    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            a, b = candidates[i], candidates[j]
            if {a.code, b.code} == {a.code, a.comparable_to} or (b.comparable_to == a.code):
                continue  # mutually exclusive variants (base vs phased), not concurrent decisions
            for kpi in sorted(_shared_kpis(db, organization_id, a, b)):
                ea, eb = _effect_on(a, kpi), _effect_on(b, kpi)
                if ea is None or eb is None or ea == 0 or eb == 0:
                    continue
                combined = ea + eb  # natural display units (pct points / pts)
                opposing = ea * eb < 0
                kind, severity = None, "LOW"
                if opposing:
                    ratio = min(abs(ea), abs(eb)) / max(abs(ea), abs(eb))
                    kind = "OPPOSING"
                    severity = "MEDIUM" if ratio >= 0.1 else "LOW"
                else:
                    floor = _GUARDRAIL_MIN.get(kpi)
                    level = _current_level(db, organization_id, kpi) if floor else None
                    if floor and level is not None and level * (1 + combined / 100.0) < floor:
                        kind, severity = "AMPLIFY_BREACH", "HIGH"
                    elif abs(combined) > 1.5 * max(abs(ea), abs(eb)):
                        kind, severity = "AMPLIFY", "MEDIUM"
                    else:
                        kind, severity = "OVERLAP", "LOW"
                note = "" if opposing else _downstream_note(db, organization_id, kpi, ea, eb)
                rows.append(DecisionCollision(
                    organization_id=organization_id,
                    investigation_id=inv.id,
                    option_ids=[a.id, b.id],
                    option_codes=[a.code, b.code],
                    affected_kpi=kpi,
                    combined_effect_pct=round(combined, 4),
                    severity=severity,
                    collision_type=kind,
                    owners=[a.owner_role, b.owner_role],
                    combined_note=note,
                    resolution_options=[
                        "Sequence with a checkpoint: restore stock first, re-check cover, then promote",
                        "Escalate combined approval to the executive with the joint exposure",
                        "Abandon or defer one of the two decisions",
                    ],
                    resolved=False,
                ))
    for r in rows:
        db.add(r)
    db.flush()
    telemetry.record_stage(db, organization_id, inv.id, "collisions", "rules", ok=True,
                           confidence_impact=-0.1 if any(r.severity == "HIGH" for r in rows) else None)
    return rows


def unresolved_high(db: Session, organization_id: str, option_id: str) -> list[DecisionCollision]:
    return [
        r for r in db.query(DecisionCollision)
        .filter(DecisionCollision.organization_id == organization_id,
                DecisionCollision.resolved.is_(False),
                DecisionCollision.severity == "HIGH")
        .all()
        if option_id in (r.option_ids or [])
    ]


def resolve_collision(db: Session, organization_id: str, collision_id: str,
                      actor_user_id: str, actor_role: str, resolution: str, note: str) -> DecisionCollision:
    row = (
        db.query(DecisionCollision)
        .filter(DecisionCollision.organization_id == organization_id,
                DecisionCollision.id == collision_id)
        .first()
    )
    if row is None:
        raise AppError("NOT_FOUND", "Collision not found", 404)
    if resolution not in ("SEQUENCE", "ESCALATE_COMBINED", "ABANDON_ONE"):
        raise AppError("BAD_REQUEST", "resolution must be SEQUENCE | ESCALATE_COMBINED | ABANDON_ONE", 400)
    if len((note or "").strip()) < 10:
        raise AppError("BAD_REQUEST",
                       "A resolution note (≥ 10 chars) is required — humans resolve, the system never auto-optimizes", 400)
    row.resolved = True
    row.resolution = resolution
    row.resolution_note = note
    row.resolved_by_role = actor_role
    db.add(row)
    audit(db, organization_id=organization_id, actor_user_id=actor_user_id, actor_role=actor_role,
          action="collision.resolve", object_type="decision_collision", object_id=row.id,
          details={"resolution": resolution, "severity": row.severity})
    db.flush()
    return row


def serialize_collision(r: DecisionCollision) -> dict:
    return {
        "id": r.id,
        "investigation_id": r.investigation_id,
        "option_codes": r.option_codes,
        "affected_kpi": r.affected_kpi,
        "combined_effect_pct": r.combined_effect_pct,
        "severity": r.severity,
        "collision_type": r.collision_type,
        "owners": r.owners,
        "combined_note": r.combined_note,
        "resolution_options": r.resolution_options,
        "resolved": r.resolved,
        "resolution": r.resolution,
        "resolution_note": r.resolution_note,
        "resolved_by_role": r.resolved_by_role,
    }
