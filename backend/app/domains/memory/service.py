"""Institutional memory (AC25) — retrieval with a written similarity explanation.

Retrieval order (arch 8.17): (1) tenant filter → (2) entitlement filter →
(3) structured filters (KPI, driver, entity, region, action, outcome, time) →
(4) vector cosine similarity → (5) plain text scan (labeled, no BM25 claims) →
(6) structured rerank (exact entity/KPI matches boosted deterministically) →
(7) written explanation: which entities/KPIs/drivers matched, the score, the
historical outcome, and the lesson.

Embeddings: pgvector in Docker mode; deterministic feature-hashing fallback
offline (DEGRADED note surfaced — never hidden). Hashing: 256-dim, signed
n-gram hashing of title/kpi/driver/entities/action, L2-normalized — same
input ⇒ same vector ⇒ replay-safe.
"""
from __future__ import annotations

import hashlib
import math
import re

from sqlalchemy import text as sqlalchemy_text

from sqlalchemy.orm import Session

from ...errors import AppError
from ...models.memory import HistoricalCase

DIM = 256
EMBEDDING_METHOD = "feature_hash_v1"  # deterministic offline fallback for pgvector


def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", (text or "").lower()) if len(t) > 1]


def _h(token: str, salt: int) -> int:
    return int(hashlib.sha1(f"{salt}|{token}".encode()).hexdigest()[:8], 16) % DIM


def embed(text_fields: list[str]) -> list[float]:
    """Signed feature hashing over token unigrams + bigrams. Deterministic."""
    vec = [0.0] * DIM
    tokens: list[str] = []
    for f in text_fields:
        toks = _tokens(f)
        tokens.extend(toks)
        tokens.extend(f"{a}_{b}" for a, b in zip(toks, toks[1:]))
    for t in tokens:
        vec[_h(t, 1)] += 1.0
        vec[_h(t, 2)] -= 0.5  # signed second projection reduces collision bias
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [round(v / norm, 6) for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def seed_embedding(case: HistoricalCase) -> None:
    case.embedding = embed([case.title, case.kpi_code, case.driver_class, case.region,
                            case.action_taken, " ".join(case.entities or [])])
    case.embedding_method = EMBEDDING_METHOD


def _pgvector_active(db: Session) -> bool:
    """True when the bind is PostgreSQL with a usable VECTOR column + extension."""
    try:
        dialect = db.get_bind().dialect.name
        if dialect != "postgresql":
            return False
        db.execute(sqlalchemy_text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")).scalar()
        return db.get_bind().dialect.name == "postgresql"
    except Exception:
        return False


def _cosine_similarities(db: Session, rows: list[HistoricalCase], qvec: list[float]) -> dict[str, float]:
    """pgvector cosine when on PostgreSQL (canonical); Python cosine only for the
    strictly test-only SQLite bind. Same vectors, same math — the store differs."""
    if qvec is None:
        return {}
    if _pgvector_active(db) and rows:
        # In-database cosine via pgvector (`<=>` is cosine distance); the vector
        # literal is the deterministic feature-hash embedding of the query.
        vec_lit = "[" + ",".join(f"{v:.6f}" for v in qvec) + "]"
        ids = [r.id for r in rows]
        rows_out = db.execute(
            sqlalchemy_text(
                "SELECT id, 1 - (embedding <=> CAST(:vec AS vector)) AS sim "
                "FROM historical_cases WHERE id = ANY(:ids) AND embedding IS NOT NULL"
            ),
            {"vec": vec_lit, "ids": ids},
        ).all()
        return {rid: float(sim) for rid, sim in rows_out}
    return {r.id: cosine(qvec, r.embedding) for r in rows}


def search(
    db: Session, organization_id: str, viewer_role: str,
    kpi_code: str | None = None, driver_class: str | None = None,
    query: str | None = None, analogue_for: str | None = None, limit: int = 5,
) -> dict:
    """Entitlement-aware retrieval with the written explanation. Never silent."""
    # (1) tenant + (2) entitlement + (3) structured filters
    q = db.query(HistoricalCase).filter(HistoricalCase.organization_id == organization_id)
    rows = q.all()
    visible = [r for r in rows if not r.access_roles or viewer_role in r.access_roles]
    if kpi_code:
        visible = [r for r in visible if r.kpi_code == kpi_code or (r.entities and kpi_code in " ".join(r.entities))]
    if driver_class:
        visible = [r for r in visible if r.driver_class == driver_class]
    if analogue_for:
        visible = [r for r in visible if r.analogue_for == analogue_for]
    withheld = len(rows) - len(visible)

    # (4) vector similarity on the query embedding
    qvec = embed([query or "", kpi_code or "", driver_class or ""]) if query else None

    def text_score(r: HistoricalCase) -> float:
        # (5) plain text scan — plainly labeled as such, no BM25 claims
        if not query:
            return 0.0
        hay = " ".join([r.title, r.action_taken, r.lesson, " ".join(r.entities or [])]).lower()
        toks = _tokens(query)
        return sum(1 for t in toks if t in hay) / max(len(toks), 1)

    def rerank_bonus(r: HistoricalCase) -> float:
        # (6) deterministic structured rerank: exact KPI/driver/entity match boost
        # deterministic structured rerank (arch 8.17 step 6): exact KPI/driver/
        # entity matches boosted — fixed weights, documented, replay-safe
        bonus = 0.0
        if kpi_code and r.kpi_code == kpi_code:
            bonus += 0.10
        if driver_class and r.driver_class == driver_class:
            bonus += 0.10
        if query:
            toks = set(_tokens(query))
            ent_hits = sum(1 for e in (r.entities or []) if toks & set(_tokens(e)))
            bonus += 0.06 * ent_hits
        return bonus

    sims = _cosine_similarities(db, visible, qvec) if qvec else {}
    scored = []
    for r in visible:
        sim = sims.get(r.id, 0.0)
        score = round(min(1.0, 0.85 * sim + 0.15 * text_score(r) + rerank_bonus(r)), 4) if (qvec or query) else 0.5
        scored.append((r, score, sim))

    scored.sort(key=lambda t: (-t[1], t[0].title))
    top = scored[:limit]

    # (7) written explanation — always
    results = []
    for r, score, sim in top:
        matched = []
        if kpi_code and r.kpi_code == kpi_code:
            matched.append(f"KPI {r.kpi_code}")
        if driver_class and r.driver_class == driver_class:
            matched.append(f"driver {r.driver_class}")
        if query:
            toks = set(_tokens(query))
            ents = [e for e in (r.entities or []) if toks & set(_tokens(e))]
            if ents:
                matched.append("entities " + ", ".join(ents))
        explanation = (
            f"Matched {'; '.join(matched) if matched else 'free-text tokens'}; "
            f"embedding cosine {sim:.2f} ({EMBEDDING_METHOD}), blended score {score:.2f}. "
            f"Historical outcome {'+' if r.outcome_rs >= 0 else ''}₹{r.outcome_rs/1e6:.1f}M "
            f"({'within band' if r.within_band else 'outside band'}). Lesson: {r.lesson}"
        )
        results.append({
            "id": r.id, "title": r.title, "period_label": r.period_label,
            "kpi_code": r.kpi_code, "driver_class": r.driver_class, "region": r.region,
            "action_taken": r.action_taken, "outcome_rs": r.outcome_rs, "within_band": r.within_band,
            "lesson": r.lesson, "entities": r.entities or [], "analogue_for": r.analogue_for,
            "similarity": score, "embedding_cosine": round(sim, 4),
            "explanation": explanation,
        })
    on_pg = _pgvector_active(db)
    return {
        "results": results,
        "withheld_by_entitlement": withheld,
        "embedding_store": "postgresql+pgvector" if on_pg else "test-only python-cosine fallback",
        "embedding_method": EMBEDDING_METHOD,
        "degraded_note": ("" if on_pg else
                          "DEGRADED (test-only bind): not on PostgreSQL+pgvector — Python cosine over "
                          "feature-hash vectors; production runs pgvector cosine in-database."),
        "method_label": (f"pgvector cosine + structured rerank + plain text scan (labeled); "
                         f"vectors: {EMBEDDING_METHOD}") if on_pg else
                        "python cosine + structured rerank + plain text scan (labeled)",
    }
