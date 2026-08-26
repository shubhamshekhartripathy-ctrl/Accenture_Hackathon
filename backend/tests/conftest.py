"""Test fixtures.

PostgreSQL (with pgvector) is the DEFAULT test engine — tests run against the
same database as production. Set TEST_DATABASE_URL (or RF_TEST_DATABASE_URL)
to point elsewhere; the URL below assumes the docker compose Postgres is
reachable on localhost:5432. If (and only if) no PostgreSQL is reachable, the
suite falls back to a throwaway SQLite file — a strictly TEST-ONLY escape
hatch, loudly labeled, never used at runtime.
"""
from __future__ import annotations

import os
import tempfile

TEST_DB_KIND = "postgresql"


def _configure_database() -> None:
    global TEST_DB_KIND
    from sqlalchemy import create_engine

    pg_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("RF_TEST_DATABASE_URL") or \
        "postgresql+psycopg://reasonflow:reasonflow@localhost:5432/reasonflow_test"
    try:
        probe = create_engine(pg_url, pool_pre_ping=True)
        from sqlalchemy import text

        with probe.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine = probe
        TEST_DB_KIND = "postgresql"
        url = pg_url
    except Exception:
        _fd, sqlite_path = tempfile.mkstemp(suffix=".db")
        url = f"sqlite:///{sqlite_path}"
        engine = create_engine(
            url, connect_args={"check_same_thread": False}, pool_pre_ping=True
        )
        TEST_DB_KIND = "sqlite-testonly"
        print(f"\n[conftest] NO POSTGRESQL REACHABLE at {pg_url} — falling back to SQLite "
              f"TEST-ONLY database {sqlite_path}. Runtime/demo must use PostgreSQL.\n")

    os.environ["DATABASE_URL"] = url
    os.environ["SECRET_KEY"] = "test-secret-key"
    os.environ["SEED_ON_BOOT"] = "1"

    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

    import app.config as config_module

    config_module.settings = config_module.Settings(
        database_url=url, secret_key="test-secret-key", seed_on_boot=True,
        redis_url=None,  # tests verify degraded-state reporting; Redis must be absent
        login_rate_per_minute=10_000,  # the limiter itself is tested in test_auth_security
    )

    import app.db as db_module

    db_module.engine = engine
    db_module.SessionLocal = db_module.sessionmaker(
        bind=engine, autoflush=False, expire_on_commit=False
    )


_configure_database()


from fastapi.testclient import TestClient  # noqa: E402

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def seeded_database():
    """Clean schema + deterministic seed exactly once, before any test (API or unit)."""
    from app.db import Base, engine
    from app.seed.seed import run_seed

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    # Stamp alembic_version so app lifespan's run_migrations() is a no-op
    from alembic.config import Config
    from alembic import command as alembic_command
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    alembic_cfg_path = os.path.join(base_dir, "alembic.ini")
    if os.path.exists(alembic_cfg_path):
        alembic_cfg = Config(alembic_cfg_path)
        alembic_cfg.set_main_option("script_location", os.path.join(base_dir, "alembic"))
        alembic_cfg.set_main_option("sqlalchemy.url", str(engine.url))
        alembic_command.stamp(alembic_cfg, "head")
    run_seed()
    yield


@pytest.fixture(scope="session")
def client():
    from app.main import create_app

    app = create_app()
    with TestClient(app) as tc:
        yield tc


PERSONAS = {
    "executive": "priya.ceo@apexfoods.example",
    "supply_chain": "rahul.sc@apexfoods.example",
    "analyst": "meera.analyst@apexfoods.example",
    "owner": "vikram.owner@apexfoods.example",
    "admin": "arjun.admin@apexfoods.example",
    "outsider": "sneha.exec@meridian.example",
}
PASSWORD = "ReasonFlow#2026"


@pytest.fixture(scope="session")
def login(client):
    _cache: dict[str, dict] = {}

    def _login(persona: str) -> dict:
        if persona not in _cache:  # cache tokens: the rate limiter is real and correctly aggressive
            resp = client.post(
                "/api/v1/auth/login", json={"email": PERSONAS[persona], "password": PASSWORD}
            )
            assert resp.status_code == 200, resp.text
            _cache[persona] = resp.json()["data"]
        return _cache[persona]

    return _login


@pytest.fixture(scope="session")
def auth_headers(login):
    def _headers(persona: str) -> dict:
        data = login(persona)
        return {"Authorization": f"Bearer {data['access_token']}"}

    return _headers

