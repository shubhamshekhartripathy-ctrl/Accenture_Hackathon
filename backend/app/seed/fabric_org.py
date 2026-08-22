"""Seed fabric: organizations, personas, source systems (spec §19.1, arch T.2).

Everything is deterministic and idempotent (upsert by natural key) so the demo
is reproducible and `docker compose up` seeds exactly once.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models.org import Organization, User
from ..models.source import SourceSystem
from ..security.passwords import hash_password

DEMO_PASSWORD = "ReasonFlow#2026"  # documented in README

PERSONAS = [
    # (email, name, role, job_title, region_scope)
    ("priya.ceo@apexfoods.example", "Priya Sharma", "EXECUTIVE", "Chief Executive Officer", []),
    ("rahul.sc@apexfoods.example", "Rahul Verma", "SUPPLY_CHAIN", "Supply Chain Manager — Northeast", ["NE"]),
    ("meera.analyst@apexfoods.example", "Meera Iyer", "ANALYST", "Senior BI Analyst", []),
    ("vikram.owner@apexfoods.example", "Vikram Rao", "KPI_OWNER", "KPI Owner — Revenue & Availability", []),
    ("arjun.admin@apexfoods.example", "Arjun Nair", "ADMIN", "Platform Administrator", []),
]

# Five heterogeneous sources with deliberate cadence/grain/lag differences (arch T.2)
SOURCES = [
    ("erp", "Apex ERP", "ERP", "daily", "SKU x DC", 0, "INTERNAL", "erp.sales_lines — invoiced net sales at source"),
    ("gl", "Finance GL Close", "FinanceClose", "monthly", "company x account", 0, "RESTRICTED", "gl.revenue_accounts — recognized revenue, accrual-adjusted at close"),
    ("pos", "POS Retail Audit", "RetailAudit", "weekly", "region x category", 6, "INTERNAL", "pos.audit_panel — third-party shelf audit, 6-day publish lag"),
    ("wms", "Warehouse Mgmt System", "WMS", "daily", "SKU x DC", 0, "INTERNAL", "wms.stock_positions — end-of-day on-hand and cover"),
    ("scorecard", "Supplier Scorecard", "SupplierScorecard", "weekly", "supplier x region", 1, "SENSITIVE", "scm.supplier_scorecards — OTIF and delay events per supplier"),
]

MERIDIAN_SOURCES = [
    ("merch_erp", "Meridian ERP", "ERP", "daily", "SKU x store", 0, "INTERNAL", "merch.sales"),
    ("merch_pos", "Meridian POS", "RetailAudit", "weekly", "region x category", 2, "INTERNAL", "merch.pos"),
]


def ensure_org(db: Session, name: str, slug: str, industry: str = "FMCG") -> Organization:
    org = db.query(Organization).filter(Organization.slug == slug).first()
    if org is None:
        org = Organization(name=name, slug=slug, industry=industry)
        db.add(org)
        db.flush()
    return org


def ensure_users(db: Session, org: Organization) -> list[User]:
    users = []
    for email, name, role, title, scope in PERSONAS:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            pw_hash, salt, iters = hash_password(DEMO_PASSWORD)
            user = User(
                organization_id=org.id,
                email=email,
                full_name=name,
                role=role,
                job_title=title,
                region_scope=scope,
                password_hash=pw_hash,
                password_salt=salt,
                pbkdf2_iterations=iters,
            )
            db.add(user)
            db.flush()
        users.append(user)
    return users


def ensure_sources(db: Session, org: Organization) -> dict[str, SourceSystem]:
    out = {}
    for code, name, kind, cadence, grain, lag, classification, lineage in SOURCES:
        src = db.query(SourceSystem).filter(
            SourceSystem.organization_id == org.id, SourceSystem.code == code
        ).first()
        if src is None:
            src = SourceSystem(
                organization_id=org.id,
                code=code,
                name=name,
                kind=kind,
                cadence=cadence,
                grain=grain,
                publish_lag_days=lag,
                data_classification=classification,
                lineage_note=lineage,
            )
            db.add(src)
            db.flush()
        out[code] = src
    return out


def ensure_meridian(db: Session) -> Organization:
    """Second tenant — proves isolation in tests and security suite."""
    org = ensure_org(db, "Meridian Retail", "meridian", industry="Retail")
    user = db.query(User).filter(User.email == "sneha.exec@meridian.example").first()
    if user is None:
        pw_hash, salt, iters = hash_password(DEMO_PASSWORD)
        user = User(
            organization_id=org.id,
            email="sneha.exec@meridian.example",
            full_name="Sneha Kulkarni",
            role="EXECUTIVE",
            job_title="Chief Merchandising Officer",
            region_scope=[],
            password_hash=pw_hash,
            password_salt=salt,
            pbkdf2_iterations=iters,
        )
        db.add(user)
        db.flush()
    for code, name, kind, cadence, grain, lag, classification, lineage in MERIDIAN_SOURCES:
        if db.query(SourceSystem).filter(SourceSystem.organization_id == org.id, SourceSystem.code == code).first() is None:
            db.add(
                SourceSystem(
                    organization_id=org.id, code=code, name=name, kind=kind, cadence=cadence,
                    grain=grain, publish_lag_days=lag, data_classification=classification, lineage_note=lineage,
                )
            )
            db.flush()
    return org
