from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import JSONType
from .base import Base, IdMixin, OrgMixin, TimestampMixin

# Evidence access states (arch H.5) — restricted evidence is COUNTED, never hidden.
EVIDENCE_STATES = ("SUPPORTING", "CONTRADICTING", "STALE", "RESTRICTED")

# Data classification bounds which model classes may process the text (arch O.2).
CLASSIFICATIONS = ("PUBLIC", "INTERNAL", "SENSITIVE", "RESTRICTED")


class EvidenceRecord(Base, OrgMixin):
    """A real evidence document linked to a KPI movement (arch H.5, T.2).

    Chain: case → this record → declared SourceSystem → timestamp → freshness →
    lineage → analytical method → data classification. No evidence without a
    source; polarity/weights are seeded facts of the fabric (never invented at
    scoring time); claims are extracted text spans with polarity.
    """

    __tablename__ = "evidence_records"
    __table_args__ = (Index("ix_evidence_kpi_driver", "kpi_code", "driver_class"),)

    doc_key: Mapped[str] = mapped_column(String(60), unique=True)
    title: Mapped[str] = mapped_column(String(160))
    kpi_code: Mapped[str] = mapped_column(String(40), index=True)
    driver_class: Mapped[str] = mapped_column(String(40), index=True)  # hypothesis class this doc speaks to
    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("source_systems.id"))
    polarity: Mapped[str] = mapped_column(String(16))  # SUPPORTS | CONTRADICTS | NEUTRAL
    support_weight: Mapped[float] = mapped_column(Float, default=0.0)     # 0..1 evidence mass
    contradiction_weight: Mapped[float] = mapped_column(Float, default=0.0)
    freshness_score: Mapped[float] = mapped_column(Float, default=1.0)    # 1 = current; decays beyond tolerance
    age_days: Mapped[int] = mapped_column(Integer, default=0)
    occurred_at_days: Mapped[int] = mapped_column(Integer, default=0)     # age relative to DEMO clock at ingest
    data_classification: Mapped[str] = mapped_column(String(16), default="INTERNAL")
    access_roles: Mapped[list] = mapped_column(JSONType, default=list)  # roles that may open the doc; [] = all
    lineage: Mapped[str] = mapped_column(String(200), default="")   # openable source reference
    method: Mapped[str] = mapped_column(String(60), default="document")
    summary: Mapped[str] = mapped_column(String(300), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    claims: Mapped[list] = mapped_column(JSONType, default=list)  # [{claim, polarity, span}] — extracted, labeled

    source = relationship("SourceSystem", lazy="joined")


class PatternReliability(Base, OrgMixin):
    """Empirical reliability of a hypothesis pattern class (arch M.1).

    The pattern prior used by hypothesis scoring; updated by structured feedback
    and outcomes through the governed proposal workflow — never silently.
    """

    __tablename__ = "pattern_reliability"

    pattern_class: Mapped[str] = mapped_column(String(40), index=True)
    n_observations: Mapped[int] = mapped_column(Integer, default=0)
    hits: Mapped[int] = mapped_column(Integer, default=0)
    prior: Mapped[float] = mapped_column(Float, default=0.5)
    last_feedback_at: Mapped[str | None] = mapped_column(String(40), nullable=True)


class InvestigationHypothesis(Base, OrgMixin):
    """A competing hypothesis for an investigated movement (arch H.3 step 3–6).

    Deterministic scoring: balance/freshness/agreement/prior are all computed
    from evidence rows and the pattern table; the LLM (when enabled) drafts
    wording only. Rank 1 is the lead.
    """

    __tablename__ = "investigation_hypotheses"
    __table_args__ = (Index("ix_hyp_inv", "investigation_id"),)

    investigation_id: Mapped[str] = mapped_column(String(36), ForeignKey("investigations.id"), index=True)
    kpi_id: Mapped[str] = mapped_column(String(36), ForeignKey("kpis.id"))
    code: Mapped[str] = mapped_column(String(40))
    statement: Mapped[str] = mapped_column(Text)
    driver_code: Mapped[str] = mapped_column(String(40), default="")
    pattern_class: Mapped[str] = mapped_column(String(40))
    support_mass: Mapped[float] = mapped_column(Float, default=0.0)
    contradiction_mass: Mapped[float] = mapped_column(Float, default=0.0)
    balance: Mapped[float] = mapped_column(Float, default=0.0)
    freshness_avg: Mapped[float] = mapped_column(Float, default=0.0)
    source_agreement: Mapped[float] = mapped_column(Float, default=0.0)
    pattern_prior: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)      # raw
    final_confidence: Mapped[float] = mapped_column(Float, default=0.0)  # × confidence_cap for the lead
    rank: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")
    reasoning_path: Mapped[list] = mapped_column(JSONType, default=list)  # graph chain — query-backed, not a graph page
    evidence_counts: Mapped[dict] = mapped_column(JSONType, default=dict)  # supporting/contradicting/stale/restricted


class HypothesisEvidence(Base, OrgMixin):
    """Link hypothesis ↔ evidence with the state shown in the evidence columns."""

    __tablename__ = "hypothesis_evidence"
    __table_args__ = (Index("ix_hev_hyp", "hypothesis_id"),)

    investigation_id: Mapped[str] = mapped_column(String(36), index=True)
    hypothesis_id: Mapped[str] = mapped_column(String(36), ForeignKey("investigation_hypotheses.id"), index=True)
    evidence_id: Mapped[str] = mapped_column(String(36), ForeignKey("evidence_records.id"), index=True)
    state: Mapped[str] = mapped_column(String(16))  # SUPPORTING | CONTRADICTING | STALE | RESTRICTED
    weight: Mapped[float] = mapped_column(Float, default=0.0)

    evidence = relationship("EvidenceRecord", lazy="joined")
