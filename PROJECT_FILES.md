# ReasonFlow — Complete Project File Inventory

**Project:** ReasonFlow — Governed KPI-to-Decision Platform (Phase 3 build)
**Stack:** FastAPI + Pydantic v2 + SQLAlchemy 2 (backend) · React 18 + TypeScript strict + Vite + Tailwind (frontend) · PostgreSQL 16/pgvector + Redis via Docker Compose (SQLite/in-process fallbacks for zero-config dev)
**Status:** Slices S1 + S2 complete (of 12, §10 of the master prompt) — 82 backend tests + 10 frontend tests green
**Repo root:** `/home/user/reasonflow/` · **Total hand-written source:** ~8,360 lines across 90 files

The pipeline implemented so far: **CONTRACT → RECONCILE → DETECT → TRIAGE** (S1 + S2), with the investigation runner, SSE streaming and stage telemetry in place. EXPLAIN / DECIDE / LEARN land in S3–S12.

---

## 1. Repository root

| File | What it is |
|---|---|
| `README.md` | Quick start (local + Docker), seeded login accounts, test commands, S1 security model summary, slice status list. |
| `IMPLEMENTATION_PLAN.md` | The living plan required by the master prompt: §0 reference-state verification, §1 component→slice→status table, §2 target repo tree, §3 slice dependency chain, §4–5 slice records. Each completed slice records what was built, locked-target verification results, test counts, justified deviations, and risks for the next slice. **This is the authoritative progress log.** |
| `docker-compose.yml` | Three services: `api` (FastAPI app), `db` (`pgvector/pgvector:pg16` with healthcheck), `redis` (cache/event bus). Wired for the production-shaped local run. |
| `docker/db-init/01-extensions.sql` | Idempotent extension bootstrap for Postgres (`pgvector`, `pgcrypto`) executed on first DB boot. |
| `backend/Dockerfile` | Python 3.13-slim image, installs `requirements.txt`, runs uvicorn with the app's lifespan seed. |

---

## 2. Backend — application core (`backend/app/`)

| File (lines) | What it does |
|---|---|
| `config.py` (57) | Pydantic settings: DB URL (SQLite default), Redis URL, JWT secret, AI-provider credentials, `DEMO_NOW` clock. Detects degraded states (no Postgres / no Redis / no AI creds) so `/health/ready` can report them loudly. |
| `db.py` (62) | SQLAlchemy 2 engine + session factory, Postgres/SQLite dialect handling, lifespan `create_all` + idempotent seed hook. |
| `envelope.py` (20) | The uniform response envelope `{ data, meta }` every router returns (frontend client is shaped to it). |
| `errors.py` (73) | Typed app errors (ApiError with status/code/message), the global exception handler that converts them to envelopes — silent failures are structurally discouraged. |
| `main.py` (70) | FastAPI app assembly: CORS, security dependency, lifespan (create_all + seed), mounts all routers (auth, contracts, scenarios, kpis, health, reconcile, investigations, queue), degraded-state boot banner. |

---

## 3. Backend — data models (`backend/app/models/`, SQLAlchemy 2 ORM)

| File (lines) | Models defined |
|---|---|
| `base.py` (32) | Declarative Base, IdMixin (UUID), OrgMixin (org scoping + timestamps) — org-multi-tenancy enforced at row level. |
| `org.py` (60) | `Organization`, `User` (5 roles: EXECUTIVE/ANALYST/KPI_OWNER/SUPPLY_CHAIN/ADMIN, region_scope, password hash), `AuditEvent` (who/what/when/before-after JSON — every governed action is audited). |
| `source.py` (25) | `SourceSystem` — declared data feeds (erp, gl, pos, wms, campaign, audit scorecard) with data classification and expected cadence/grain. |
| `kpi.py` (21) | `Kpi` — code, name, category, region, unit; one governed contract per KPI. |
| `contract.py` (164) | `KpiContract` + 7 satellites: `ContractSource` (lineage path, authoritative flag, expected grain/cadence, tolerance), `ContractDriver` (direction, prior weight, hypothesis class, rank), `ContractThreshold` (expected band, warning/critical deviation, **exposure ₹ per point, margin weight, strategic weight, min_history, cold_start_flag, floor_band**), `ContractRight` (per-role may_recommend/simulate/approve + approve limit + escalation), `ContractEntitlement` (row scope, masked columns), `KpiRelation` (typed causal links with elasticity/confidence/lag), `ContractVersion` (immutable snapshot per version with change reason). |
| `observation.py` (38) | `KpiObservation` — the planted事实 data: kpi × source × period_key, value, occurred_at, grain, calendar_key, freshness_age_days. |
| `reconciliation.py` (55) | `ReconciliationRun` (verdict, reliability_score, confidence_cap, working_value + working_source + justification, penalties JSON, freshness profile) and `ReconciliationConflict` (typed conflict cards: definition/refresh/grain/coverage/hierarchy/calendar, severity, values both sides, confidence impact, routed owner, resolution state + mandatory note). |
| `detection.py` (60) | `DetectionResult` — baseline, deviation, robust_z, anomaly, CI bounds, history count, cold_start flag, method + model version (replayable). |
| `investigation.py` (83) | `Investigation` (workflow_state machine, pinned contract_version, period, reliability/cap carried through, last_error) + `InvestigationStageEvent` (from→to state per stage, ok, message) — the persisted spine of the Transparency Ledger. |
| `scenario.py` (41) | `ScenarioTemplate` + `ScenarioInstance` — config-only scenario definitions (drivers/guardrails/options/materiality/dataset refs as JSON), the AC18 "one engine, many configs" substrate. |
| `telemetry.py` (34) | `StageTelemetry` — one row per pipeline stage: stage code, deterministic vs LLM flag, tokens, cost estimate, latency. |
| `__init__.py` (20) | Registers every model so `create_all` sees them. |

---

## 4. Backend — security (`backend/app/security/`)

| File (lines) | What it does |
|---|---|
| `passwords.py` (17) | PBKDF2 hashing/verification (hashlib, dependency-free). |
| `jwt_auth.py` (60) | HS256 JWT encode/decode implemented with std-lib hmac (documented S1 deviation), expiry + role claims. |
| `deps.py` (88) | FastAPI dependencies: `get_current_user` (Bearer token → User), role guards per endpoint class, org scoping helper, login rate limiter (10/min in-process; Redis upgrade noted for S6). |

---

## 5. Backend — domain logic (`backend/app/domains/`)

| File (lines) | What it does |
|---|---|
| `contracts/service.py` (516) | Contract governance: CRUD with **versioned edits** (immutable snapshot per version), status machine DRAFT→ACTIVE→CONFLICTED→UNDER_REVIEW→ACTIVE (illegal transitions 409), activation gated on blocking gaps, **loud gap report** (NO_SOURCES, NO_THRESHOLDS, NO_DRIVERS, NO_RIGHTS, NO_OWNER, FORMULA_CONFLICT [MAJOR — governed-but-degraded], NO_GUARDRAILS), `assert_contract_ready` = the AC1 gate (DRAFT/UNDER_REVIEW refused, ACTIVE/CONFLICTED proceed with certainty capped), full serialization with satellites. |
| `scenarios/service.py` (192) | Scenario templates: list/detail/start with loud validation (contract missing/not ready, source/KPI/guardrails missing → nothing half-provisioned); CONFLICTED contracts produce a non-blocking warning; idempotent start creates the workspace + audit event. |
| `reconcile/engine.py` (246) | The locked reliability math: penalties — definition 0.12; stale 0.00/.06/.12/.15 by days beyond cadence tolerance (≤2/3–5/6–9/≥10; tolerance +2d daily-weekly, +3d monthly); grain 0.05 (incl. cross-source coarse-grain, once per cycle, suppressed when a definition conflict already covers the pair); coverage 0.10; hierarchy 0.08; calendar 0.05. `reliability = clamp(1−Σ, 0.4, 1.0)`; verdict CONFLICTED iff open definition conflict or reliability < 0.75; `confidence cap = reliability + 0.10`; working value = authoritative source with a written justification ("deferred — not merged", never a silent merge). |
| `reconcile/service.py` (286) | Gathers per-source readings for the latest period (resolved by MAX(occurred_at), never lexicographic period keys); **freshness = age of the source's newest observation for the KPI** (a feed property); opens/updates typed conflict cards; owner resolution with mandatory audited note; re-run recomputes from observations. |
| `detect/engine.py` (70) | Deterministic statistics: seasonal-median baseline with MAD-scaled robust z, 95% CI = baseline ± 2σ̂, anomaly flag, cold-start when history < min_history. No ML dependencies — fully replayable. |
| `detect/service.py` (190) | Series assembly (ordered by occurred_at), baseline persistence, detection artifact write, method/model_version stamping. |
| `triage/engine.py` (93) | Materiality: `significance = clamp((max(robust_z, 6·anomaly)−2)/4, 0, 1)`; `impact = |dev|·exposure + margin/strategic weights`; `score = significance × clamp(log1p(impact)/10)`; bands ≥0.70 CRITICAL / ≥0.40 ELEVATED / ≥0.15 WATCH / else NOISE; **governance floor_band may raise a band** (recorded `floored: true`, never lowered); cold start → monitor-only; KPIs without thresholds are statistical-only, never CRITICAL. Returns the full arithmetic dict shown in the UI "Why?" panel. |
| `investigations/service.py` (208) | Runs the S2 pipeline prefix through the runner: pins contract version, executes reconcile→detect→triage, persists stage events + telemetry, exposes workflow state, resume-from-last-good-artifact, cold-start mode. |
| `queue/service.py` (103) | The executive attention queue: aggregates latest detection + materiality per KPI, sorts CRITICAL→ELEVATED→WATCH→NOISE then score, **cold start pinned last** (monitor-only, not an attention demand). `GET` serves stored artifacts only; `POST /refresh` is the real computation (audited + telemetered). |
| `__init__.py` files | Package markers. |

---

## 6. Backend — pipeline services (`backend/app/services/`)

| File (lines) | What it does |
|---|---|
| `pipeline/runner.py` (96) | Stage/RunContext abstraction + state transitions CONTRACT_READY→RECONCILING→RECONCILED→DETECTING→DETECTED→TRIAGED; failure → `last_error` + FAILED state + SSE `stage_failed`; refresh resumes from last-good artifact (deterministic replay). |
| `pipeline/events.py` (46) | Buffered SSE bus: per-run deque (200 events), named events (`reconciliation_complete`, `prefix_complete`, …), 15s keepalives, replay for late subscribers, single `done` close. Safe operational text only (tests assert no chain-of-thought vocabulary). |
| `telemetry.py` (83) | StageTelemetry writer: stage code, deterministic/LLM flag, tokens, cost, latency — the raw material of the Transparency Ledger (S11 UI). |
| `audit.py` (35) | AuditEvent writer used by every governed mutation. |

---

## 7. Backend — API routers (`backend/app/routers/`)

| File (lines) | Endpoints |
|---|---|
| `auth.py` (94) | `POST /auth/login` (rate-limited), `POST /auth/refresh`, `GET /auth/me`. |
| `contracts.py` (168) | `GET/POST /contracts`, `GET/PATCH /contracts/{id}` (PATCH = KPI_OWNER/ADMIN), `POST …/activate`, `GET …/status`, `GET …/versions`, `GET …/gaps`; second contract per KPI → 409 CONTRACT_EXISTS. |
| `reconcile.py` (229) | `POST /contracts/{id}/reconcile`, `GET …/reconcile/latest` (conflict cards + freshness profile embedded), `POST /conflicts/{id}/resolve`, `GET/POST /queue`, `POST /investigations`, `GET /investigations`, `GET /investigations/{id}/events` (SSE with replay). |
| `kpis.py` (99) | `GET /kpis` (portfolio with ACTIVE/CONFLICTED/COLD START chips), `GET /kpis/{id}`. |
| `scenarios.py` (45) | `GET /scenarios`, `GET …/{id}`, `POST …/{id}/start`. |
| `health.py` (75) | `/health/live`, `/health/ready` — reports degraded states (SQLite fallback / no Redis / deterministic LLM) loudly, never silently. |

---

## 8. Backend — seed & deterministic fabric (`backend/app/seed/`)

| File (lines) | What it fabricates (all idempotent, all deterministic) |
|---|---|
| `seed.py` (47) | Orchestrates org → users → sources → KPIs+contracts → **observations** → scenarios; safe to run on every boot. |
| `fabric_org.py` (124) | Apex Foods + Meridian Retail (isolation tenant); 5 personas + admin + outsider (logins in README); rate-limit-safe password hashing. |
| `fabric_kpis.py` (389) | 7 KPI contracts with full satellite sets: revenue NE (hero: exposure ₹716,667/point → ₹8.6M at −12%, strategic 0.8; ERP/GL/POS sources with grains), OSA NE, inventory cover NE, marketing ROI (**floor_band WATCH**), supplier reliability, sales-per-outlet South, millet noodles launch (cold_start flag). Drivers with priors (supplier_delay 0.62, competitor_promo 0.12, marketing 0.08, seasonality 0.04), rights (SC approve limit ₹2M; analyst may not approve), entitlements (SC masked columns unit_cost_rs + marketing_roi, NE row scope). ERP expected_grain documented as "SKU x DC → period agg" to match the feed as delivered. |
| `fabric_observations.py` (122) | The planted 14-week history behind the hero demo. `values = baseline + (σ_target/0.7413)·BASE13` where BASE13 is a fixed median-0/MAD-0.5 shape ⇒ **exact baselines and deviations by construction**. σ targets: revenue 2.2239 (95.45→84.0), OSA 4.42 (90.8→71.4), inventory 1.71 (11.6→5.1), marketing 0.0592 (3.10→2.976), supplier 4.27 (94.0→81.2), South 6.50 (210.0→199.8). Planted events: **GL 87.0 @P14** (definition conflict vs ERP 84.0), **POS revenue stale 16d** (7d beyond weekly+2 → exactly the 0.12 bracket), POS panel normal 8d lag, **South ERP 202.9 cross-grain + South POS stale 15d**, millet 5 periods → COLD START. DEMO_NOW = 2026-08-10 UTC; per-feed lag is an explicit fabric parameter. |
| `fabric_scenarios.py` (251) | 3 scenario templates (T.1 set: supplier-delay, competitor-promo, marketing-mix) — pure configuration: drivers, guardrails, options, materiality, entitlements, dataset + ground-truth refs. Zero per-scenario code paths (AC18). |

---

## 9. Backend — tests (`backend/tests/`, 82 tests)

| File (tests) | Covers |
|---|---|
| `conftest.py` | Import-time DB patching (SQLite), session-scoped DB, cached persona tokens (avoids rate limiter), deterministic clock. |
| `test_auth_security.py` (13) | Login/refresh/me, wrong tenant, bad password, rate limit, role claims. |
| `test_contracts.py` (8) | CRUD, versioning, status machine, CONTRACT_EXISTS 409, PATCH RBAC. |
| `test_gap_report.py` (8) | Every gap code fires with its stored effect/banner; FORMULA_CONFLICT is MAJOR not blocking. |
| `test_ac1_gate.py` (3) | AC1: DRAFT/UNDER_REVIEW refused for reasoning; ACTIVE and CONFLICTED-but-capped proceed. |
| `test_scenarios.py` (8) | Template list/detail, loud validation failures, idempotent start, warnings path. |
| `test_tenant_isolation.py` (6) | Meridian cannot see Apex anything (kpis, contracts, observations). |
| `test_reconcile_unit.py` (11) | Penalty schedule brackets, tolerance math, cap, verdict rule, grain suppression, working-value choice. |
| `test_reconcile_integration.py` (7) | **Locked targets end-to-end on the fabric**: reliability 0.76 / cap 0.86 / working 84.0 / "deferred, not merged"; South 0.83 with stale+grain penalties; resolution flow restores and re-prices. |
| `test_detect_triage_unit.py` (9) | Baseline/MAD/CI math, cold-start flag, band boundaries, governance floor (`floored: true`), statistical-only KPIs never CRITICAL. |
| `test_queue.py` (4) | Landing beat (CRITICAL revenue first, millet pinned last), refresh computes + audits, floored WATCH. |
| `test_investigation_pipeline.py` (5) | Full prefix to TRIAGED, pinned version, failure → FAILED + SSE `stage_failed`, telemetry rows (0 LLM stages, 100% numbers without LLM), replay/resume from artifact. |

---

## 10. Frontend (`frontend/`)

| File (lines) | What it is |
|---|---|
| `vite.config.ts` (25) | Vite + React plugin, `/api` proxy to :8000 (browser code never calls localhost directly), allowedHosts for the sandbox preview, strict TS project refs. |
| `tailwind.config.ts` (59) | Token-mapped theme: deep-ink palette, single gold accent, semantic tones (pass/fail/warn/info), tabular-nums utility. |
| `src/styles/tokens.css` | Design tokens (colors, focus rings, reduced-motion) — single source for Tailwind mapping. |
| `src/api/client.ts` (71) | Envelope-aware fetch wrapper: Bearer attach, 401 → login redirect, typed `get/post`, ApiError with status+code. |
| `src/api/types.ts` (38) | Shared payload types (KpiRow, QueueEntry). |
| `src/auth/store.ts` (61) | Session persistence (localStorage), typed session shape. |
| `src/components/ui.tsx` (191) | Primitive kit: Card, Chip (tone-mapped), Banner, Tabs, EmptyState, ErrorState, Skeleton, statusTone. |
| `src/components/Shell.tsx` (85) | App frame: nav (Overview/KPIs/Scenarios + Ledger/Memory tagged S11/S9), session header. |
| `src/components/DemoBar.tsx` (82) | Persona switcher (real audited re-auth). Future demo actions (inject POS error, fast-forward, toggle LLM, reset) are **visibly disabled with slice tags** — honest placeholders, no fake buttons. |
| `src/App.tsx` (48) | Router: /login, authed shell with routes to Overview, Kpis, CaseFile, Scenarios. |
| `src/pages/Login.tsx` (104) | Real auth form + demo persona quick-select; error states tested. |
| `src/pages/Overview.tsx` (197) | **The executive landing beat (S2)**: real materiality queue — CRITICAL-dominant ordering, exposure (₹8.6M headline), band chips, "Why {band}?" arithmetic drill-down (significance/impact/score, floored note), cold-start KPIs in a separate monitor-only section pinned last, Refresh = POST /queue/refresh. |
| `src/pages/Kpis.tsx` (86) | KPI Intelligence table: portfolio with contract status + COLD START chips. |
| `src/pages/CaseFile.tsx` (240) | **The central experience**: sticky §11A status header (current value + deviation, materiality band, certainty slot [S5-tagged], reliability, contract status/version), blocking-gap gate banner, 5 persistent tabs — Contract (real), Reconciliation (real), Investigation (real prefix), Decisions (S7 placeholder), History (S9 placeholder). |
| `src/pages/CaseFileContract.tsx` (185) | Full contract renderer: definition, formula + note, sources w/ lineage & grains, drivers w/ priors, threshold/guardrail weights, rights matrix, entitlements, version history. |
| `src/pages/CaseFileReconcile.tsx` (239) | **Moment 1 UI**: verdict banner ("Your inputs disagree." + reliability/cap), working value with justification, typed conflict cards with values/impact/routing and **owner resolution with required note**, freshness profile (age vs cadence, discounted sources flagged), run/re-run. |
| `src/pages/CaseFileInvestigation.tsx` (185) | Investigation runner: start pipeline (analyst/admin), state chip, detection stats (baseline/deviation/z/CI/history/cold start), materiality, stage timeline, stage telemetry panel (0 LLM / 100% w/o LLM / latency), SSE progress line, retry on FAILED. |
| `src/pages/Scenarios.tsx` (134) | Scenario cards with engine identity (`reasonflow-core`), configuration transparency, start flow. |
| `src/tests/` (3 files, 10 tests) | Login (3), ContractTab (4, incl. loud-degradation), OverviewQueue (3: dominant CRITICAL + INPUTS CONFLICT chip, arithmetic drill-down, governance-floor note). `setup.ts` = jsdom + jest-dom. |

---

## 11. What is real vs. deliberately not built yet

**Real now (no mocks):** auth/RBAC/tenancy, contract governance with versioning and gap gates, the seeded observation fabric, reconciliation with the locked penalty math, deterministic detection (median/MAD/CI), materiality triage with governance floors, the executive queue, the investigation pipeline prefix with persisted stages + telemetry + SSE, the full UI above. Every number in the UI comes from the API.

**Not built yet (honest placeholders, slice-tagged in the UI):** EXPLAIN decomposition/hypotheses/certainty (S3–S5), scenario simulation (S6), decision workspace + approvals (S7), outcomes/learning (S9), Transparency Ledger UI + Memory (S11), demo inject/fast-forward controls (S5/S9/S10/S12). In deterministic mode (no AI credentials), LLM-assisted stages run deterministic templates and are labeled as such.
