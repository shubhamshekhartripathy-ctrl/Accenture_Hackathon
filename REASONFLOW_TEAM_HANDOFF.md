# ReasonFlow — Team Handoff / Continuation

## Project

**Repository:**

`C:\Users\Soham\Documents\reasonflow-round2_final`

Do **not** rebuild the project, redesign the architecture, restart S1–S12, or assume previous completion claims are correct without checking the current repository.

---

## 1. Read These Files First

Read completely, in this order:

1. `REASONFLOW_ROUND2_PRODUCT_SPEC.md`
2. `REASONFLOW_ROUND2_ARCHITECTURE (3).md`
3. `REASONFLOW_MASTER_PHASE3_CODING_PROMPT_FINAL_V3(1).md`
4. `IMPLEMENTATION_PLAN.md`
5. `PROJECT_FILES.md`
6. `docs/UI_UX_AUDIT.md`
7. `docs/UI_UX_FINAL_QA.md`
8. `docs/FINAL_ACCEPTANCE_QA.md`
9. `final_acceptance_results.json`
10. `ROOT_CAUSE_REPORT.md` — especially important for the latest unresolved runtime issues
11. `walkthrough.md` / `walkthrough*.md` if present

Also inspect:
- current `git status`
- recent Git commits
- current Docker/Compose configuration

These files are the source of truth for the product, architecture, acceptance criteria, and previous implementation work.

---

## 2. Current Project Status

The project implementation is substantially complete.

### Infrastructure
- PostgreSQL 16 ✅
- pgvector ✅
- Redis ✅
- FastAPI ✅
- React/Vite ✅
- Docker Compose ✅

### Backend
- S1–S12 implemented ✅
- PostgreSQL canonical runtime ✅
- pgvector institutional memory ✅
- Redis/cache ✅
- deterministic reasoning ✅
- LLM routing/fallback ✅
- RBAC / decision rights ✅
- guardrails ✅
- second-order impacts ✅
- collisions ✅
- contract evolution ✅
- telemetry ✅

### Automated backend validation
- Full PostgreSQL suite: **145/145 passed** ✅

### Frontend validation
- TypeScript typecheck ✅
- Vitest: **12/12 passed** ✅
- Production build ✅
- UI/UX productization substantially completed ✅

### Acceptance
- AC1–AC26 have been mapped in QA artifacts.
- Hero scenario and no-reset reproducibility have been tested previously.
- Persona flows have been tested previously.

**Important:** Do not blindly trust old “complete” reports. Manual browser testing later exposed real frontend integration problems.

---

## 3. Latest Proven Root Causes

A focused root-cause investigation was performed without changing code.

### Root Cause A — Stale GET Cache

**File:** `frontend/src/api/client.ts`

**Problem:** GET requests used by `demo-refresh` and other state reloads could return stale browser-cached responses.

**Observed path:**

Mutation succeeds → refresh event fires → GET returns stale response → React receives unchanged data → UI appears stale/non-functional.

**Fix already implemented:**

```ts
cache: "no-store"
```

in the shared fetch request.

### Root Cause B — Scenario KPI Response Envelope Mismatch

**File:** `frontend/src/pages/Scenarios.tsx`

**Problem:** The API client already unwraps backend response envelopes, so:

```ts
api.get("/kpis")
```

returns the KPI array directly.

Old behavior expected:

```ts
kpis.data.find(...)
```

which caused a runtime `TypeError`.

**Effect:** Scenario start succeeds → KPI request succeeds → code crashes while reading `kpis.data` → navigation never happens.

**Fix already implemented:**

Use:

```ts
kpis.find(...)
```

and preserve the real investigation/KPI navigation flow.

### Root Cause C — PostgreSQL Reset Lock Contention

**File:** `backend/app/services/demo.py`

**Problem:** The reset endpoint kept a request-scoped SQLAlchemy DB session active while performing destructive schema operations such as `drop_all()`.

PostgreSQL could wait for an exclusive lock.

**Effect:** `POST /demo/reset` hangs/timeouts and other DB operations can queue behind the lock.

**Fix already implemented:** Reset no longer holds the conflicting request DB session while schema reset runs.

---

## 4. Additional File to Review

A change was also made to:

`backend/app/routers/aigov.py`

Inspect why it was changed and whether it is required. Do not remove it blindly or make unrelated changes.

---

## 5. Important Runtime Discovery

A previous runtime investigation found that the live API container had been running for approximately 36 hours and was using an **old backend image/state**.

A stale PostgreSQL transaction was holding a lock on `kpi_contracts`, causing:
- login requests to hang
- reset to hang
- misleading browser behavior

After restarting the stale API:
- login succeeded

However, the old running backend still reproduced the reset hang.

**Critical implication:** validate the current source-code fixes against a freshly built and running Docker stack. Do not diagnose current source code against an old container.

---

## 6. Immediate Remaining Task

### Validate the Three Root-Cause Fixes in a Fresh Runtime

From the project root:

```powershell
docker compose down
docker compose up -d --build
docker compose ps
curl.exe http://localhost:8000/api/v1/health/ready
```

Expected:
- postgres healthy
- redis healthy
- api running
- ui running
- readiness = ready
- postgres/pgvector/redis = ok

---

## 7. Required Runtime Tests

### A. DemoBar

Test in the real browser:
- Inject POS
- Fast-forward 14d
- Toggle LLM
- Reset

For every action:

**CLICK → real HTTP request → correct response → backend/demo state change → fresh GET → visible UI update**

Reset must not hang.

### B. Open Investigation

Test:

**Rahul Verma / SUPPLY_CHAIN**  
Scenarios → Revenue Northeast → Open Investigation

Then:

**Vikram Rao / KPI_OWNER**  
→ same flow

Expected:
- scenario starts
- primary KPI is found
- investigation is created/loaded
- navigation reaches `/kpis/{id}`
- Investigation tab contains real data

### C. Decisions

Check:
- EXECUTIVE
- ANALYST
- SUPPLY_CHAIN
- KPI_OWNER

Verify:
- authorized action succeeds
- unauthorized action receives backend denial
- guardrail FAIL blocks approval
- successful action refreshes persisted state

### D. Reconciliation

Verify:

Run reconciliation → real request → real response → persisted reconciliation → visible UI update.

### E. History

Verify:
- outcomes
- feedback
- proposals
- memory/history

Must use real backend data or a meaningful empty state.

### F. Ledger

Verify:
- telemetry
- routes
- cache status
- LLM state
- updates after actions

---

## 8. Automated Regression

Run:

```powershell
npm run typecheck
npx vitest run
npm run build
docker compose exec -w /srv/app api sh -c "PYTHONPATH=/srv/app pytest -q"
```

Expected backend result:

**145 passed**

Do not weaken, skip, delete, or renumber tests.

---

## 9. Do Not Repeat the Previous Mistake

Previous agents repeatedly did:

**guess root cause → edit several files → tests pass → claim fixed → real browser remains broken**

Do not do this again.

If a flow still fails:

1. reproduce it
2. inspect DOM/button state
3. inspect network request
4. inspect request/response
5. inspect backend logs
6. inspect database state
7. identify exact failing layer
8. only then make the smallest fix
9. rerun the affected flow

Never claim success from automated tests alone.

---

## 10. Data / Memory Context

The prototype already contains deterministic Apex Foods seed data under:

`backend/app/seed/`

including:
- KPI fabric
- scenarios
- evidence
- observations
- memory
- organization/personas

Persistent historical memory is stored in PostgreSQL:

```text
public.historical_cases
```

Important fields include:
- `title`
- `period_label`
- `kpi_code`
- `driver_class`
- `region`
- `action_taken`
- `outcome_rs`
- `within_band`
- `lesson`
- `entities`
- `access_roles`
- `analogue_for`
- `embedding`
- `embedding_method`
- `embedding_version`
- `organization_id`
- timestamps

The memory embedding is:

```text
vector(256)
```

Do **not** start searching for or downloading a new dataset for ReasonFlow. The current prototype already has deterministic business data and persisted memory.

---

## 11. Final Goal

The finished product must satisfy:

**REAL BACKEND STATE**  
→ **REAL USER CLICK**  
→ **REAL API**  
→ **REAL PERSISTENCE**  
→ **REAL UI UPDATE**

Then verify:
- all four personas
- DemoBar
- Scenario flow
- Reconciliation
- Investigation
- Decisions
- History
- Ledger
- Memory

Only after the runtime issues are resolved should the final AC1–AC26 acceptance report be treated as final.

### Final rule

Do not start another large redesign.

Start by:
1. reading the listed files,
2. inspecting current Git state,
3. checking current runtime,
4. rebuilding Docker stack,
5. validating the three proven root-cause fixes,
6. then testing the remaining persona/UI flows.
