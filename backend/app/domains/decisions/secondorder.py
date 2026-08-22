"""Second-order impact (AC20) — graph_elasticity propagation.

Implements the architecture rule exactly:
    effect(child)     = parent_effect × edge.elasticity      (documented multiplicative model)
    confidence(child) = Π edge confidences × horizon factor  (edge lag vs option horizon)
    bounds            widen 20% (relative) per hop
    dependency_path   = the edge chain — persisted and rendered, never decorative
    method            = "graph_elasticity"

Graph = `kpi_relations` (governed KPI↔KPI edges, per the architecture) ∪
`impact_edges` (edges into derived downstream impact metrics — nodes without
contracts). Node metadata carries kind (KPI | DERIVED_IMPACT) and unit so the
UI can label pts vs pct honestly.

Effects are carried in each node's NATURAL DISPLAY UNITS (PCT nodes in
percentage points, PTS nodes in points) — the architecture's own arithmetic:
    promotion → revenue +8 → inventory +8 × −2.25 = −18 (pct pts)
              → stockout −18 × −0.667 = +12.0 pts → complaints +12 × 0.583 = +7.0 pct pts
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ...models.contract import KpiContract, KpiRelation
from ...models.decisions import DecisionOption
from ...models.impacts import ImpactEdge, ImpactMetric
from ...models.investigation import Investigation
from ...models.kpi import Kpi

WIDEN_PER_HOP = 0.20  # relative uncertainty widening per hop (compounds)


def _nodes(db: Session, organization_id: str) -> dict[str, dict]:
    """code → {kind, unit} for every node in the propagation graph."""
    nodes: dict[str, dict] = {}
    for k in db.query(Kpi).filter(Kpi.organization_id == organization_id).all():
        nodes[k.code] = {"kind": "KPI", "unit": k.unit}
    for m in db.query(ImpactMetric).filter(ImpactMetric.organization_id == organization_id).all():
        nodes[m.code] = {"kind": "DERIVED_IMPACT", "unit": m.unit, "name": m.name, "provenance": m.provenance}
    return nodes


def _edges(db: Session, organization_id: str) -> list[dict]:
    """Union graph edges: kpi_relations (KPI↔KPI) + impact_edges (derived nodes)."""
    contract_codes: dict[str, str | None] = {
        c.id: (c.kpi.code if c.kpi else None)
        for c in db.query(KpiContract).filter(KpiContract.organization_id == organization_id).all()
    }
    edges: list[dict] = []
    for rel in db.query(KpiRelation).filter(KpiRelation.organization_id == organization_id).all():
        a, b = contract_codes.get(rel.a_contract_id), contract_codes.get(rel.b_contract_id)
        if a and b and rel.relation in ("IMPACTS", "PRECEDES"):
            edges.append({"parent": a, "child": b, "elasticity": rel.elasticity,
                          "confidence": rel.confidence, "lag_days": rel.lag_days, "source": "kpi_relations"})
    for e in db.query(ImpactEdge).filter(ImpactEdge.organization_id == organization_id).all():
        edges.append({"parent": e.parent_code, "child": e.child_code, "elasticity": e.elasticity,
                      "confidence": e.confidence, "lag_days": e.lag_days, "source": "impact_edges"})
    return edges


def propagate(db: Session, organization_id: str, inv: Investigation,
              option: DecisionOption) -> list[dict]:
    """Deterministic BFS from the option's declared direct effects."""
    sim = option.simulation or {}
    direct_pct: dict = (sim.get("inputs", {}).get("deltas", {}) or {}).get("direct_pct", {})
    if not direct_pct:
        return []

    # Phased options may suppress an edge (documented, config-driven): e.g. the
    # restore-then-promote variant absorbs the promo drain in the restored buffer.
    suppress = set(map(tuple, (sim.get("inputs", {}).get("deltas", {}) or {}).get("suppress_edges", [])))

    nodes = _nodes(db, organization_id)
    by_parent: dict[str, list[dict]] = {}
    for e in _edges(db, organization_id):
        if (e["parent"], e["child"]) in suppress:
            continue
        by_parent.setdefault(e["parent"], []).append(e)

    horizon = option.horizon_days or 42
    results: list[dict] = []
    # frontier: (code, effect_pct, confidence, hops, path, lag_sum)
    frontier: list[tuple[str, float, float, int, list[str], int]] = [
        (code, float(pct), 1.0, 0, [code], 0) for code, pct in direct_pct.items()
    ]
    enqueued: set[tuple[str, ...]] = {tuple(f[4]) for f in frontier}
    while frontier:
        code, effect, confidence, hops, path, lag_sum = frontier.pop(0)
        if hops > 0:
            horizon_factor = round(min(1.0, horizon / max(lag_sum, 1)), 3)
            widen = WIDEN_PER_HOP * hops
            meta = nodes.get(code, {"kind": "KPI", "unit": None})
            unit = meta.get("unit")
            suffix = " pts" if unit == "PTS" else "%"
            results.append({
                "kpi": code,
                "node_kind": meta["kind"],          # KPI | DERIVED_IMPACT
                "unit": unit,                       # PTS / PCT / DAYS … (natural display units)
                "provenance": meta.get("provenance"),
                "effect_pct": round(effect, 4),
                "effect_display": f"{effect:+.1f}{suffix}",
                "bounds_pct": sorted([round(effect * (1 - widen), 4), round(effect * (1 + widen), 4)]),
                "confidence": round(confidence * horizon_factor, 4),
                "horizon_factor": horizon_factor,
                "dependency_path": path,
                "hops": hops,
                "method": "graph_elasticity",
            })
        for e in by_parent.get(code, []):
            child = e["child"]
            new_path = path + [child]
            if tuple(new_path) in enqueued or child in path:
                continue  # no cycles, no repeated paths
            enqueued.add(tuple(new_path))
            frontier.append((
                child,
                effect * e["elasticity"],
                confidence * e["confidence"],
                hops + 1,
                new_path,
                lag_sum + e["lag_days"],
            ))
    results.sort(key=lambda r: (len(r["dependency_path"]), r["kpi"]))
    return results


def annotate_options(db: Session, organization_id: str, inv: Investigation,
                     options: list[DecisionOption]) -> None:
    """Persist second_order rows into each option's simulation snapshot."""
    for o in options:
        so = propagate(db, organization_id, inv, o)
        sim = dict(o.simulation or {})
        sim["second_order"] = {
            "method": "graph_elasticity",
            "rule": "effect = parent × elasticity (natural display units); confidence = Π edge confidences × horizon factor",
            "widening": f"{int(WIDEN_PER_HOP * 100)}%/hop (relative, compounds)",
            "effects": so,
        }
        o.simulation = sim
        db.add(o)
    db.flush()
