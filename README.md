# ReasonFlow — Governed Decision Intelligence for Operations

ReasonFlow is an enterprise decision-intelligence platform that turns operational signals into **governed, explainable, auditable decisions**.

> **Detect the right problem → reconcile the truth → reason deterministically → evaluate safe actions → enforce decision rights → capture outcomes → learn from history.**

This repository contains the Round 2 full-stack prototype for the Apex Foods FMCG operating environment, using PostgreSQL + pgvector + Redis with a React/Vite decision workspace.

## Why ReasonFlow?

Traditional analytics products often stop at dashboards and alerts. ReasonFlow continues through the decision lifecycle:

```text
Operational signals
        ↓
Detection & materiality
        ↓
Contract governance
        ↓
Source reconciliation
        ↓
Investigation
        ↓
Hypotheses + evidence
        ↓
Deterministic reasoning
        ↓
Decision options
        ↓
Server-side simulation
        ↓
Guardrails + second-order impacts
        ↓
Decision rights + human approval
        ↓
Outcome + feedback
        ↓
Institutional memory
```

AI is deliberately bounded. Numerical conclusions remain deterministic, while LLM capabilities are constrained by routing policy, governance, guardrails, and auditability.

## Core Capabilities

### 1. Governed KPI Contracts

Every KPI is backed by a contract defining what must be true before investigation:

- KPI definition and formula
- source systems
- thresholds
- owners and drivers
- decision rights
- entitlements
- versions
- audit history

A KPI cannot simply jump into reasoning without the required governance state.

### 2. Multi-Source Reconciliation

ReasonFlow supports heterogeneous operational sources that can disagree.

Example:

```text
ERP:      ₹84.0M
Finance:  ₹87.0M
POS:      stale / delayed
WMS:      current
```

The reconciliation layer identifies disagreement and feeds reliability/confidence effects into downstream reasoning.

### 3. Detection & Materiality

KPI movement is classified into materiality bands such as:

- `CRITICAL`
- `ELEVATED`
- `WATCH`
- `NOISE`

Materiality is evaluated before downstream reasoning.

### 4. Deterministic Investigation

The core quantitative reasoning does not require an LLM.

The deterministic pipeline supports:

- robust statistical detection
- decomposition
- residual checks
- confidence bounds
- cold-start handling
- abstention
- replayable reasoning

### 5. Hypotheses & Evidence

Investigations contain competing hypotheses.

Evidence can carry:

- support / contradiction
- source
- freshness
- method
- lineage
- reliability
- confidence effects

This creates a traceable reasoning chain instead of an opaque generated explanation.

### 6. Decision Workspace

ReasonFlow generates structured decision options from predefined contractual levers.

Example options include:

- backup supplier
- air freight
- price promotion
- phased promotion
- inventory actions

Each option can expose:

- expected impact
- range
- cost
- horizon
- guardrails
- second-order impacts
- decision rights
- approval status
- collision state

The system prevents an LLM from inventing arbitrary business levers.

### 7. Server-Side Simulation & Guardrails

Decision simulation runs on the server.

An option can be:

- `PASS`
- `WARNING`
- `FAIL`
- `NOT_SAFE`
- `UNKNOWN`

Hard guardrail failures block approval at the backend.

Example:

```text
Promotion
   ↓
higher sales
   ↓
inventory cover falls below required bound
   ↓
NOT_SAFE / FAIL
   ↓
approval blocked
```

### 8. Decision Rights & Human Approval

Decision authority is role-aware.

Demo personas:

| Name | Role |
|---|---|
| Meera Iyer | `ANALYST` |
| Priya Sharma | `EXECUTIVE` |
| Vikram Rao | `KPI_OWNER` |
| Rahul Verma | `SUPPLY_CHAIN` |

The backend is authoritative for:

- approval rights
- escalation
- blocked actions
- overrides
- entitlements

AI does not auto-merge governed decisions.

### 9. Second-Order Impacts & Collisions

ReasonFlow models consequences beyond the immediate KPI.

It can identify:

- downstream KPI effects
- resource depletion
- service-level effects
- shared-lever conflicts
- mutually exclusive decisions

A collision can become a governed human-resolution workflow.

### 10. Outcomes & Feedback

The lifecycle continues after approval.

ReasonFlow records:

- expected result
- actual result
- variance
- outcome band
- feedback
- reliability updates
- governed contract proposals

This creates a closed decision-learning loop.

### 11. Institutional Memory with PostgreSQL + pgvector

Historical decision cases are persisted in PostgreSQL.

Primary memory table:

```text
public.historical_cases
```

Important fields include:

- `kpi_code`
- `driver_class`
- `action_taken`
- `outcome_rs`
- `within_band`
- `lesson`
- `entities`
- `access_roles`
- `organization_id`
- `embedding`
- `embedding_method`
- `embedding_version`

The embedding column is:

```text
vector(256)
```

Historical cases can be retrieved by similarity while respecting organizational/entitlement boundaries.

Initial historical memory is provided by the deterministic seed fabric under:

```text
backend/app/seed/
```

### 12. Transparency & AI Governance

The transparency layer records structured pipeline telemetry such as:

- execution stage
- latency
- model/route
- fallback
- cache behavior
- token/cost information when applicable
- routing decisions
- degraded states

### 13. Multiple Scenarios, One Engine

The same reasoning engine handles different operating scenarios.

Examples:

- Revenue Decline — Northeast
- Inventory / Manufacturing Delay
- Millet Noodles cold-start / new-product scenario

The scenario configuration changes while the underlying engine remains shared.

## Architecture

```text
┌──────────────────────────────────────────────────────────────┐
│                        React / Vite UI                       │
│                                                              │
│ Scenarios → Overview → KPI Case File → Decision Workspace  │
│ Investigation → Reconciliation → History → Memory → Ledger │
└──────────────────────────────┬───────────────────────────────┘
                               │
                         REST / SSE
                               │
┌──────────────────────────────▼───────────────────────────────┐
│                           FastAPI                            │
│                                                              │
│ Auth / RBAC                                                 │
│ Contracts                                                   │
│ Detection / Triage                                         │
│ Reconciliation                                              │
│ Investigation                                               │
│ Decisions                                                   │
│ Outcomes / Feedback                                         │
│ Memory                                                      │
│ AI Governance / Telemetry                                  │
│ Demo / Scenario control                                    │
└───────────────┬──────────────────────┬───────────────────────┘
                │                      │
                ▼                      ▼
        ┌───────────────┐      ┌───────────────┐
        │ PostgreSQL 16 │      │ Redis 7       │
        │ + pgvector    │      │ Cache / rate  │
        └───────────────┘      └───────────────┘
```

PostgreSQL is the canonical application store. Alembic is the migration mechanism.

## Technology Stack

### Frontend
- React
- TypeScript
- Vite
- Tailwind CSS
- Vitest

### Backend
- Python
- FastAPI
- SQLAlchemy 2
- Pydantic
- Alembic
- psycopg 3

### Data / Infrastructure
- PostgreSQL 16
- pgvector
- Redis 7
- Docker Compose

### AI
- deterministic reasoning baseline
- configurable LLM routing
- policy/capability-aware routing
- fallback / degraded behavior
- AI usage telemetry

## Repository Structure

```text
reasonflow-round2_final/
│
├── backend/
│   ├── app/
│   │   ├── domains/
│   │   ├── routers/
│   │   ├── services/
│   │   ├── seed/
│   │   ├── memory/
│   │   ├── learning/
│   │   └── ...
│   ├── alembic/
│   ├── tests/
│   ├── alembic.ini
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── api/
│   │   ├── styles/
│   │   └── tests/
│   └── package.json
│
├── docker/
│   └── db-init/
│
├── docs/
│   ├── UI_UX_AUDIT.md
│   ├── UI_UX_FINAL_QA.md
│   └── FINAL_ACCEPTANCE_QA.md
│
├── IMPLEMENTATION_PLAN.md
├── PROJECT_FILES.md
├── docker-compose.yml
└── README.md
```

## Running Locally with Docker

### Prerequisites

Install:

- Docker Desktop
- Git

Docker Desktop must be running.

### Start

From the project root:

```powershell
docker compose up -d --build
```

Check:

```powershell
docker compose ps
```

Expected:

```text
postgres   healthy
redis      healthy
api        running
ui         running
```

### Open

Frontend:

```text
http://localhost:5173
```

FastAPI docs:

```text
http://localhost:8000/docs
```

Health:

```powershell
curl.exe http://localhost:8000/api/v1/health/ready
```

## Demo Personas

Demo password:

```text
ReasonFlow#2026
```

| Name | Email | Role |
|---|---|---|
| Meera Iyer | `meera.analyst@apexfoods.example` | `ANALYST` |
| Priya Sharma | `priya.ceo@apexfoods.example` | `EXECUTIVE` |
| Vikram Rao | `vikram.owner@apexfoods.example` | `KPI_OWNER` |
| Rahul Verma | `rahul.sc@apexfoods.example` | `SUPPLY_CHAIN` |

## Hero Scenario

The primary demo follows an Apex Foods Revenue Northeast investigation:

```text
Revenue NE material decline
        ↓
Multi-source reconciliation disagreement
        ↓
Investigation
        ↓
Decomposition + hypotheses + evidence
        ↓
Decision options
        ↓
Server-side simulation
        ↓
Guardrails
        ↓
Second-order effects
        ↓
Decision collision
        ↓
Human approval
        ↓
Outcome
        ↓
Feedback
        ↓
Governed contract evolution
        ↓
Historical memory
        ↓
Transparency
```

Cold-start / abstention behavior is also supported when evidence or confidence is insufficient.

## Testing

### Frontend

From `frontend/`:

```powershell
npm run typecheck
npx vitest run
npm run build
```

Validated baseline during development:

```text
12 frontend tests passed
typecheck passed
production build passed
```

### Backend

Inside the Docker API environment:

```powershell
docker compose exec -w /srv/app api sh -c "PYTHONPATH=/srv/app pytest -q"
```

Validated PostgreSQL baseline:

```text
145 passed
0 failed
0 errors
```

The backend test database uses PostgreSQL + pgvector, not SQLite.

## Product Validation

The project has been validated against the locked AC1–AC26 specification.

Key areas include:

- KPI governance
- heterogeneous source disagreement
- reconciliation
- materiality
- deterministic reasoning
- competing hypotheses
- evidence lineage
- abstention
- persona entitlements
- decision rights
- structured recommendations
- server-side simulation
- human approval
- outcomes
- feedback
- memory
- telemetry
- scenarios
- guardrails
- second-order impacts
- collisions
- portfolio
- governed contract evolution
- LLM routing
- pgvector memory
- semantic cache isolation

See:

```text
docs/FINAL_ACCEPTANCE_QA.md
final_acceptance_results.json
```

for current acceptance evidence.

## Design & UX

ReasonFlow uses a premium enterprise decision-intelligence visual language rather than a generic SaaS dashboard.

Design goals:

- deep near-black/ink canvas
- layered charcoal surfaces
- restrained gold/amber primary accent
- emerald / amber / rose semantic states
- indigo/violet for reasoning/AI states
- dense information hierarchy
- fine borders
- strong typography
- compact metadata
- purposeful motion
- responsive desktop-first layouts

## Core Product Principles

### Backend is the source of truth

The frontend must never fabricate business truth.

### Real interaction

A successful action follows:

```text
UI event
→ API request
→ backend computation/mutation
→ persistence
→ response/SSE
→ UI update
```

### Human governance

AI can recommend, simulate, explain, and route, but governed decisions remain under explicit human authority.

### Deterministic numeric truth

LLM usage must not silently alter deterministic numeric conclusions.

### Abstention is a feature

When evidence or confidence is insufficient, the system should clearly abstain rather than manufacture certainty.

### Learning is governed

Feedback can influence future reasoning, but contract changes require governed review and merge.

## Data & Memory

The project uses deterministic seed fabric rather than an external Kaggle-style dataset.

Seed definitions live under:

```text
backend/app/seed/
```

Persistent historical memory lives in:

```text
public.historical_cases
```

with a PostgreSQL `vector(256)` embedding field for similarity retrieval.

This means the prototype contains real persisted business inputs and generated artifacts rather than UI-only fake output.

## Current Development State

The project is at the final validation / handoff stage.

The core implementation, data fabric, PostgreSQL layer, deterministic reasoning pipeline, governance, memory, telemetry, and frontend have been extensively tested.

Recent runtime debugging identified frontend integration issues involving stale GET caching, a scenario response-envelope mismatch, and PostgreSQL reset lock contention. The fixes are documented in `ROOT_CAUSE_REPORT.md` and should be validated against a freshly built Docker runtime before treating the browser acceptance state as final.

## Continuing Development

Before changing the project:

1. Read the product specification and architecture documents.
2. Preserve the S1–S12 architecture.
3. Prefer small, isolated changes.
4. Validate backend behavior before relying on UI tests.
5. Verify real browser flows for interactive changes.
6. Never replace backend truth with hardcoded frontend outputs.
7. Keep PostgreSQL + pgvector + Redis as the canonical stack.

## License

Add the intended project/competition license here before public distribution.
