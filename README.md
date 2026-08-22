# ReasonFlow — Governed KPI-to-Decision Platform

> *"Where KPI movements become governed decisions."*
>
> **BI ends at insight. ERP begins at execution. ReasonFlow owns the governed middle** — KPI
> meaning, source reconciliation, materiality, interpretation, uncertainty, evidence, persona
> context, decision rights, action, monitoring, outcomes, and organizational memory.

Primary loop: `CONTRACT → RECONCILE → DETECT → TRIAGE → EXPLAIN → DECIDE → LEARN ↺`

Status: **Slice S1 complete** (see `IMPLEMENTATION_PLAN.md`) — KPI Contract + Scenario
Configuration + KPI Case File (Contract tab) + auth/personas + tenant isolation + audit +
telemetry foundation. Later slices add reconciliation, detection, reasoning, certainty,
personas/entitlements, decisions, guardrails, collisions, portfolio, learning, memory, the
routing gateway, semantic cache, the Transparency Ledger, and the full 12-step hero demo.

## Quick start (canonical — Docker)

```bash
docker compose up --build
# starts: PostgreSQL 16 + pgvector · Redis · FastAPI (alembic upgrade head → seed → :8000) · React UI (:5173)
```

* UI:  http://localhost:5173  ·  API + docs: http://localhost:8000/docs
* The API container runs **`alembic upgrade head`** (migrations are the canonical schema
  mechanism, including the pgvector extension bootstrap) before uvicorn; seeding is
  idempotent on first boot.
* Deterministic LLM mode needs **no API keys** — every number is computed by rules;
  "offline AI mode" still runs on PostgreSQL (it is not a SQLite mode).

## Quick start (local dev — still PostgreSQL)

```bash
# 1) Postgres 16+ with pgvector + Redis (or reuse the compose services):
docker compose up -d postgres redis

# 2) backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head                                  # migrations → PostgreSQL → pgvector
python3 -m uvicorn app.main:app --reload --port 8000  # idempotent seed on boot

# 3) frontend
cd ../frontend
npm install
npm run dev          # http://localhost:5173 (proxies /api to :8000)
```

Default `DATABASE_URL` is `postgresql+psycopg://reasonflow:reasonflow@localhost:5432/reasonflow`
(see `.env.example`). **SQLite is not a runtime option** — it exists only as an explicitly
selected, TEST-ONLY escape hatch for isolated unit runs without a database (the test
suite itself defaults to PostgreSQL).

No external credentials needed — the app boots in **deterministic mode** (LLM stages fall
back to templates), SQLite fallback (documented offline mode), and in-process cache/event
bus. `/api/v1/health/ready` reports every degraded state loudly.

## Docker (PostgreSQL 16 + pgvector + Redis)

```bash
docker compose up --build
# api :8000 · db (pgvector enabled at init) · redis
```

Seeding is idempotent: three ScenarioTemplates + the full Apex Foods fabric (5 sources,
7 KPIs with governed contracts, relations, personas, a second tenant for isolation proofs).

## Seeded accounts (password `ReasonFlow#2026`)

| Persona | Email | Role |
|---|---|---|
| Executive | `priya.ceo@apexfoods.example` | EXECUTIVE |
| Supply Chain | `rahul.sc@apexfoods.example` | SUPPLY_CHAIN (NE rows only) |
| Analyst | `meera.analyst@apexfoods.example` | ANALYST (no approval rights) |
| KPI Owner | `vikram.owner@apexfoods.example` | KPI_OWNER (contract governance) |
| Admin | `arjun.admin@apexfoods.example` | ADMIN |
| Outsider | `sneha.exec@meridian.example` | EXECUTIVE @ Meridian Retail (tenant isolation) |

## Scenarios (one engine — configuration only, AC18)

| # | Scenario | Business problem | Primary KPI |
|---|---|---|---|
| S1 | `apex_revenue_decline_ne` | Revenue Decline — Northeast (hero) | Revenue NE |
| S2 | `apex_inventory_cover` | Inventory / Availability — cover collapse | Inventory days-of-cover NE |
| S3 | `apex_millet_launch` | New product launch — sparse history (cold start) | Millet Noodles revenue |

## Testing

```bash
cd backend && python3 -m pytest tests/ -q     # 46 tests: auth, contracts, gaps, scenarios, AC1 gate, tenant isolation
cd frontend && npm run test                   # 7 component tests (Login, ContractTab)
cd frontend && npm run typecheck && npm run build
```

## Security model (S1 scope)

Real JWT auth (HS256, PBKDF2-SHA256 210k iterations) · login lockout + rate limiting ·
RBAC route guards (analyst cannot edit contracts → 403) · mandatory tenant predicate on
every query (cross-tenant → 404) · audited governed mutations (login, contract edits,
status changes, scenario starts, denied operations) · server-side truth only.

## Slice status
- S1 ✅ Contracts + scenarios + case file shell
- S2 ✅ Observation fabric, reconcile (reliability/cap/working value), detect (robust-z/CI/cold start), triage (materiality bands + governance floor), queue API + UI, investigation prefix w/ SSE + stage telemetry

