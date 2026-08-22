# REASONFLOW ROUND 2 — ARCHITECTURE & WORKING PROTOTYPE BLUEPRINT (v3 — FINAL)

**Phase:** 2 of 3 — Product Specification → **Architecture & Prototype Design** → Implementation
**Source of truth:** `REASONFLOW_ROUND2_PRODUCT_SPEC.md` (LOCKED) + official Accenture Innovation Challenge 2026 Round 2, Problem Track 3
**Audience:** the Phase 3 coding AI and the team defending the demo

**Version note (v3 — FINAL):** integrates the five improvement clusters into v2 without weakening anything: (1) Scenario / Business-Problem Configuration, (2) Guardrail KPIs, (3) Second-Order Impact & Decision Collision, (4) Decision Portfolio, (5) Enterprise AI Governance (routing gateway, model policy, governed contract merges, pgvector memory, semantic cache). All A–Z sections revised for internal consistency; the primary loop remains `CONTRACT → RECONCILE → DETECT → TRIAGE → EXPLAIN → DECIDE → LEARN`; guardrails, impact analysis, collision detection, and portfolio coordination are part of the DECIDE stage and its surrounding governance. New acceptance criteria AC18–AC26 added with tests. No code; no product reinvention.

The 12-step hero demo (+ 3 time-boxed extension beats, §T) and acceptance criteria AC1–AC26 are the binding acceptance tests of this blueprint.

---

# A. ARCHITECTURE PRINCIPLES

1. **The workflow is the product; the model is a plugin.** The architecture's centerpiece is the stage pipeline and its artifacts; the LLM is a policy-gated, metered, replaceable adapter with exactly three labeled capabilities.
2. **Every stage writes a durable, versioned artifact; every number has a labeled deterministic method; every LLM use is labeled, routed, and metered.** Enforced structurally by the pipeline runner and the routing gateway.
3. **Depth over breadth.** Modular monolith + background worker. Three configured scenarios, one coherent engine, one hero demo. No distributed infrastructure without a real execution path.
4. **One engine, many business problems.** Scenario configuration changes data, drivers, thresholds, actions, constraints, guardrails, and persona behavior — never the core engine. No scenario gets a private implementation path.
5. **Decisions are business-safe by construction.** Every action is checked against guardrail KPIs, second-order impacts, decision rights, and sibling decisions *before* a human can approve it. Approval is always human; execution is never automatic.
6. **Learning is governed, not silent.** The learning loop never mutates an active contract. It produces reviewable change proposals that only an authorized owner can merge into a new contract version.
7. **Reuse the Round 1 engine where it is already correct** (detection math, simulation equations, entity resolution, evidence grounding, reliability shrinkage, security, tenancy).
8. **Degrade loudly, never fabricate.** Every governance gap, conflict, guardrail UNKNOWN, LLM outage, cache miss, or provider failure produces a visible, auditable state.
9. **The demo is a test.** The full demo scenario must run headlessly (pytest) against seeded data — correctness is proven in CI, not rehearsed on stage.
10. **Deterministic replay.** With LLM stages in template mode, a run reproduces bit-for-bit. This is the strongest anti-hallucination and anti-drift argument available.
11. **Server-side truth.** Entitlements, simulation, guardrails, rights verdicts, routing policy, and masking are enforced in the backend. The frontend is never the security boundary.

**Critical rules (never / always):** Never — let the LLM fabricate quantitative values; silently merge conflicting sources; hide contradictory evidence; auto-execute business actions; rely on frontend-only authorization; hardcode historical cases or simulation results; fake telemetry; cache across tenants or without version validity; mutate an active contract from the learning loop; make the graph decorative. Always — persist important states; version important decisions and contracts; link claims to evidence; enforce entitlements server-side; expose uncertainty; log analytical methods and model routes; keep all demo numbers coherent; maintain deterministic fallback; make failures visible; keep the architecture understandable.

**The deeper thesis this architecture makes obvious:**

```
WHAT HAPPENED? → WHAT IS TRUSTWORTHY ENOUGH TO ACT ON? → WHO SHOULD ACT?
→ WHAT SHOULD THEY DO? → WHAT MUST WE PROTECT? → WHAT ELSE WILL THIS DECISION CHANGE?
→ DOES IT CONFLICT WITH ANOTHER DECISION? → DID IT WORK? → WHAT DID THE ORGANIZATION LEARN?
```

---

# B. SYSTEM CONTEXT

One modular monolith, one optional background worker, Redis as the semantic-cache layer, Postgres (+pgvector) as the only system of record.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        PRESENTATION — React 19 + Vite SPA                     │
│  Scenario Selector · Executive Overview (+ Decision Portfolio panel) ·        │
│  KPI Case File (Contract | Reconcile | Investigation | Decisions | History) · │
│  Transparency Ledger (with AI routing + cache views) · Memory · DemoBar       │
└───────────────────────────────────┬──────────────────────────────────────────┘
                                    │ HTTPS (relative /api) · SSE progress
┌───────────────────────────────────▼──────────────────────────────────────────┐
│                        REASONFLOW CORE API — FastAPI                          │
│  Scenario Configuration (ScenarioTemplate → contracts, sources, drivers,      │
│  guardrails, personas, entitlements, datasets)                                │
│  Core loop domains:  contracts │ reconcile │ detect │ triage │ explain       │
│  DECISION INTELLIGENCE:  decide (records · simulation · rights) │             │
│      guardrails │ second-order impacts │ collision detection │                │
│      decision_portfolio (aggregation over stored artifacts only)             │
│  LEARNING & GOVERNANCE:  learn (outcomes · feedback · proposals) │            │
│      governance (ProposedContractChange review→merge) │ memory (pgvector)     │
│  CROSS-CUTTING:  pipeline runner (telemetry-wrapped) │ persona │ entitlements ││
│      audit │ cost caps │ semantic cache (services/cache)                      │
└──────┬───────────────────────────────────────────────┬───────────────────────┘
       │                                               │
┌──────▼──────────────────┐   ┌────────────────────────▼──────────────────────┐
│  POSTGRESQL 16 + pgvector│   │  AI GOVERNANCE (services/llm)                 │
│  ALL reasoning state     │   │  Data Sensitivity + Tenant Policy + Cost     │
│  is relational; memory   │   │  Policy  →  Model Routing Gateway  →          │
│  embeddings are vectors  │   │  Model Providers (class adapters) or          │
│  in the same store       │   │  Deterministic Fallback  →  Telemetry + Cache │
└─────────────────────────┘   └────────────────────────────────────────────────┘
│ REDIS — semantic cache (validity-aware) · rate limits · SSE pub/sub           │
│ (absent ⇒ cache disabled + in-process fallbacks; graceful, logged)            │
│ BACKGROUND WORKER — in-process thread pool (optional separate process)        │
│ Seeded Demo Data Fabric — 3 ScenarioTemplates · 5 sources · planted truth     │
```

**Explicitly absent:** no Kafka/event streaming, no Neo4j, no LangGraph, no separate vector database, no microservices, no model training, no deep-learning forecasting, no live ERP integrations, no external feeds, no chatbot/NL-to-SQL, no collaboration suite, no billing/SSO, no autonomous optimization or execution.

**Why a background worker:** investigation pipelines run for seconds and must not block API threads; the worker executes pipeline runs off the request thread and publishes safe progress events over SSE (Redis pub/sub when available, in-process bus otherwise). `python -m app.worker` is the optional separate-process entrypoint; the in-process pool is the prototype default.

---

# C. DOMAIN ARCHITECTURE

### C.1 The stage pipeline — the core mechanism

The loop `CONTRACT → RECONCILE → DETECT → TRIAGE → EXPLAIN → DECIDE → LEARN` runs as a **telemetry-wrapped, artifact-emitting, replayable stage runner**. The DECIDE stage is itself a governed sub-workflow (C.3).

```python
class Stage(Protocol):
    stage_code: str              # "reconcile", "detect", ...
    method_label: MethodLabel    # "sql" | "stats" | "rules" | "ml" | "retrieval" | "llm"
    def run(ctx: RunContext) -> StageArtifact: ...   # writes via ctx.repo; never calls a provider directly
```

The **runner** executes stages sequentially and records one `stage_telemetry` row per stage: `{run_id, stage_code, method_label, llm_used, model_class, route_reason, provider, latency_ms, tokens_in, tokens_out, cost_est, cache_hit, cache_latency_saved_ms, cache_cost_avoided_rs, source_count, ok}`. This wrapper powers the Transparency Ledger. Stages call only the `LLMClient` facade, which routes through the Model Routing Gateway (Section O.3); every route decision is logged.

**Stage sequence:**

| # | Stage | Method label | Durable artifact | Spec ref |
|---|---|---|---|---|
| 0 | `contract_assert` | rules | Contract snapshot reference; gap report (rights? owner? thresholds? guardrails?) | §7.3 |
| 1 | `reconcile` | rules | `ReconciliationRun` + `Conflicts[]` + working value | §8 |
| 2 | `detect` | stats | `DetectionResult` + cold-start flag | §9.1 |
| 3 | `triage` | rules | `MaterialityScore` + band | §9 |
| 4 | `decompose` | sql | `ContributionDecomposition` rows | §10.2 |
| 5 | `hypothesize` | llm* | `Hypotheses[]` (contract-constrained, scenario-configured) | §10.2 |
| 6 | `gather` | retrieval (+llm* extraction) | `Evidence[]` with state (supporting/contradicting/stale/restricted) | §10.2 |
| 7 | `score_rank` | ml+rules | Scored hypotheses + composed confidence | §10.2 |
| 8 | `certainty` | rules | `CertaintyState` (ACT / ACT_WITH_CAUTION / CLARIFY / ABSTAIN) | §11 |
| 9 | `narrate` | llm* | `PersonaBriefs[]` (rendered from the structured conclusion object) | §13 |
| 10 | `decide` | rules+sim (sub-workflow, C.3) | Decision options → guardrail results → impact set → collision set → rights verdicts → `DecisionRecords[]` | §14–15 |
| 11 | `learn` | rules | case closure, memory embedding, calibration, **ProposedContractChange** (never a direct mutation) | §16 |

\* = LLM stages have deterministic template fallbacks and are skippable; the pipeline runs 100% without an LLM.

**Runner properties:** idempotent per run (unique stage guards) · deterministic replay with `llm_enabled=false` · per-case independence → horizontal scale by case count · failure semantics: a failed stage marks the run DEGRADED with last-good artifact — the API never invents a stage result.

### C.2 Scenario configuration flow

Scenario templates are **configurations over the shared engine**, applied at provisioning time (contracts, sources, drivers, thresholds, guardrails, options, entitlements) and at run time (driver seeds, action catalogs, persona briefs, guardrail sets):

```
ScenarioTemplate ──provision──▶ KPI Contracts + Sources + Evidence + Rights + Guardrail config
        │                                        │
        └────────run──▶ Investigations pick up scenario-configured drivers, actions, guardrails
```

One pipeline, one set of stages, one domain model — the scenario changes *data and configuration*, never code. Section T lists the three initial scenarios; AC18 tests this generality headlessly.

### C.3 The DECIDE sub-workflow

Within the pipeline, `decide` decomposes into a governed sequence of sub-stages (each with its own telemetry row):

| Sub-stage | Method | Artifact | Gate |
|---|---|---|---|
| `decide_options` | rules | candidate options (driver → lever → action) | certainty state must permit options |
| `simulate` | rules | `SimulationResult` (versioned; point + range + cost + risk + horizon) | assumption bounds |
| `guardrails_check` | rules | `DecisionGuardrail[]` per option, each PASS/WARNING/FAIL/UNKNOWN | **FAIL ⇒ option BLOCKED, cannot be approved** |
| `second_order_impact` | rules (graph elasticity) | `DecisionImpact[]` (direct + secondary, bounds, confidence, dependency path) | — |
| `collision_check` | rules | `DecisionCollision[]` vs all active/proposed decisions in the portfolio | unresolved HIGH ⇒ approval blocked until resolved |
| `rights_check` | rules | rights verdict AUTHORIZED / ESCALATE / BLOCKED | BLOCKED ⇒ not approvable |
| `decision_record` | rules | `DecisionRecord` (schema §K) | option must be APPROVABLE |
| `portfolio_update` | rules | portfolio recomputation from stored artifacts | — |

### C.4 Module map (backend/app/…)

| Module | Owns | Reuses from Round 1 |
|---|---|---|
| `domains/scenarios` | ScenarioTemplate CRUD, validation, provisioning, `POST /scenarios/{id}/start` | — (new) |
| `domains/contracts` | KPI Contracts, versions, status, sources, drivers, thresholds, rights, entitlements, gaps | — (new; anchors to Round 1 `kpi` rows) |
| `domains/reconcile` | Source ledger, conflict classifier, reliability scoring, working values | `services/entity_resolution.py` |
| `domains/detect` | Detection results, cold-start flag | `ml/detection.py` |
| `domains/triage` | Materiality scores, queue assembly | — |
| `domains/explain` | Decomposition SQL, hypotheses, evidence, scoring, certainty, reasoning paths | `engine.py` scoring, `ml/embeddings.py`, graph tables |
| `domains/decide` | Decision Records, guardrails, second-order impacts, simulation+constraints, rights, approvals, monitoring plans | `ml/simulation.py` (extended) |
| `domains/decision_portfolio` | Portfolio aggregation, collision registry, portfolio health — derived strictly from stored artifacts | — (new) |
| `domains/learn` | Outcomes+shrinkage, feedback, pattern reliability, case closure, memory (pgvector), change proposals | outcome/reliability code, memory service |
| `services/governance` | ProposedContractChange review→approve/reject→merge workflow; authorization; audit | — (new) |
| `services/pipeline` | Stage runner + telemetry capture | replaces `langgraph_flow.py` + engine orchestration |
| `services/llm` | LLMClient facade (3 capabilities) · **Model Routing Gateway** · **AI policy engine** · provider adapters · deterministic fallbacks | `ai/llm.py` (extended) |
| `services/cache` | Semantic cache (validity-aware keys, invalidation, tenant isolation, hit/miss telemetry) | — (new) |
| `services/entitlements` | Row/column/domain masking at query + serialization | `security.py` (extended) |
| `services/persona` | Persona brief assembly + numeric post-check | — |
| `services/telemetry` | Stage rows, route logs, cache metrics, cost model, cost caps, ledger API | `AgentRun` → `StageTelemetry` |
| `services/demo` | Demo controls (inject refresh, fast-forward, LLM toggle, scenario switch) — demo-mode gated | — |
| `services/worker` | Pipeline executor (in-process pool; optional separate process) | `redis_bus.py` (kept, optional) |
| `routers/*` | HTTP routes per module + auth/tenant middleware | Round 1 routers (extended) |

### C.5 Key architecture decisions (ADRs)

| Decision | Rationale | Rejected |
|---|---|---|
| Replace LangGraph with the first-party stage runner | Full control over telemetry capture, deterministic replay, failure semantics; removes a heavyweight dependency. The staging — not the framework — is the product truth | LangGraph orchestration |
| Modular monolith + background worker | Per-case stateless pipeline + tenant-scoped objects deliver the horizontal-scale story; microservices add demo risk with zero demo value | Microservices, event streaming |
| Postgres + pgvector as the only system of record | Memory embeddings live beside relational state in the same store with the same tenant/entitlement predicates; no second database to run, secure, or explain. Hashing-vector fallback keeps deterministic mode working | Pinecone/Milvus/Weaviate, Neo4j |
| Redis as the semantic-cache layer (validity-aware) | Repeats of persona narratives and safe derived artifacts are the main LLM cost; version-tagged keys make caching provably correct. Absent Redis ⇒ cache disabled (logged), never wrong | Cache-less, or naive TTL-only caching |
| Capability-based Model Routing Gateway with policy engine | Three capabilities have different cost/latency/quality needs and different data sensitivity; a policy layer (data classification × capability × tenant) makes routing defensible and observable instead of hardcoded | One model for everything; hardcoded provider names |
| Governed contract merges (ProposedContractChange) | The learning loop must be auditable and reversible; silent self-modification is an enterprise non-starter | LEARN directly mutating ACTIVE contracts |
| Scenario configuration over the shared engine | Proves generality (AC18) without forking code; judges can see the same pipeline solve a different business problem | Per-scenario code paths |
| Second-order/collision analysis as rules over the KPI-relation graph | Deterministic, explainable, cheap; no optimization solver needed — the system surfaces conflicts, humans resolve them | Autonomous optimization, digital twins |
| Seeded scenario ledger with planted ground truth | The strongest correctness demo: recover-the-truth, verified headlessly in CI | Live data, random generation |
| Custom stage runner over Airflow/Temporal | Workflows are per-case, seconds-long, and must be replayable; a workflow server is infrastructure with no demo payoff | Temporal, Airflow |

---

# D. DOMAIN MODEL

### D.1 Object catalog (field-level)

**1. KPIContract** — `kpi_contracts` + satellites (`kpi_contract_sources`, `kpi_contract_drivers`, `kpi_contract_thresholds`, `kpi_contract_rights`, `kpi_contract_entitlements`, `kpi_relations`, `contract_versions`, `contract_change_proposals`)
Fields: id · organization_id (tenant) · kpi_id · scenario_id · name · business_definition · formula_sql · formula_note · unit · business_function · owner_user_id · owner_role · status (DRAFT/ACTIVE/CONFLICTED/UNDER_REVIEW) · calendar_rule · hierarchy_config · version.
Satellites: sources (source_system_id, lineage_path, is_authoritative) · drivers (driver_code, name, direction, prior_weight, source[config|feedback], hypothesis_class) · thresholds (expected_lo, expected_hi, warning, critical, exposure_rs_per_point, margin_weight, strategic_weight, min_history, cold_start_flag) · rights (role, action_class, approve_limit_rs, escalate_to_role) · entitlements (role, row_scope json, masked_columns json, domains) · relations (a_contract_id, b_contract_id, relation[IMPACTS|PRECEDES|COMPONENT], elasticity, confidence, lag_days — used by second-order analysis) · proposals (Section D.7) · versions (full snapshot per edit).
**Why it exists:** the single governed definition preventing interpretation drift, constraining the hypothesis/action space, anchoring entitlements/rights/guardrails, and absorbing everything learned. **How it affects reasoning:** hypotheses connect to contract drivers; actions must pass rights *and guardrails*; entitlements resolve per request; second-order propagation follows contract relations. **How it evolves:** every edit is a versioned snapshot; learning never mutates ACTIVE — it produces proposals merged by an authorized owner (Section M.2). Investigations pin the `contract_version` used at investigation time, so every conclusion is reproducible against its governing definition.

**2. ScenarioTemplate** — `scenario_templates`
Fields: id · tenant_id (or global) · industry · business_problem · primary_kpi · related_kpis · source_configuration (per-source cadence, grain, publish lag) · driver_configuration · threshold_configuration · materiality_configuration · decision_options · guardrail_configuration (guardrail KPIs + thresholds + policy per FAIL/UNKNOWN/WARNING) · persona_configuration · entitlement_configuration · dataset_ref (seed) · expected_outcome_ref (planted ground truth) · scenario_description · demo_priority · version · status (DRAFT/ACTIVE/DEPRECATED).
**Why it exists:** proves the engine is a general KPI-to-decision engine, not a revenue-decline application; makes demos repeatable; gives judges a one-screen view of "what problem is configured." **Rule:** no separate implementations — a scenario changes configuration only.

**3. KPIObservation** — `kpi_observations` (CHANGE: + source_id, period_key, calendar_key)
kpi_id · organization_id · timestamp · period_key · calendar_key · entity_id (canonical) · value · source_id · grain · freshness_age_days · quality_state · checksum.

**4. ReconciliationRecord** — `reconciliation_runs` + `reconciliation_conflicts`
Run: contract_id · run_ts · verdict (CONSISTENT/MINOR/CONFLICTED) · reliability_score · working_value · working_source_id · working_justification.
Conflict: run_id · conflict_type · source_a_id · source_b_id · value_a · value_b · severity · confidence_impact · routed_to_user_id · resolution_state · resolved_at.

**5. DetectionResult** — `detection_results` (KEEP)
current_value · baseline · expected_value · confidence_interval · deviation_pct · robust_z · anomaly_score · statistical_significance · method · model_version · timestamp · cold_start_flag.

**6. MaterialityAssessment** — `materiality_scores`
detection_id · significance · exposure_rs · margin_weight · strategic_weight · risk_factor · threshold_comparison · score · band (CRITICAL/ELEVATED/WATCH/NOISE) · arithmetic json.

**7. KPIInvestigation** — `investigations` (CHANGE: + movement_ref, cold_start_mode, workflow_state, **contract_version**)
kpi_id · movement ref · contract_version (pinned) · stage events · decomposition → `contribution_decompositions` · hypotheses → `investigation_hypotheses` · evidence → `evidence` · certainty → `certainty_states` · decision options → `decision_records` · workflow_state (Section Q) · actors · timestamps.

**8. Hypothesis** — `investigation_hypotheses` (CHANGE: + hypothesis_class, pattern_prior)
statement · driver_code · support_score · contradiction_score · confidence · evidence references · graph_path · temporal_alignment · pattern_prior · status.

**9. EvidenceRecord** — `evidence_sources` + `evidence` (CHANGE: + state, freshness, relevance, **data_classification**)
source_id → document (content · checksum · occurred_at · lineage · **data_classification** PUBLIC/INTERNAL/SENSITIVE/RESTRICTED) · timestamp · freshness_age_days · evidence_type · state (SUPPORTING/CONTRADICTING/STALE/RESTRICTED) · relevance_score · analytical_method · access_scope. Data classification feeds the AI policy engine (Section O.2).

**10. DecisionRecord** — `decision_records` (NEW; supersedes Round 1 `decision_options`)
driver_code · lever_code · action_text · **target_kpi_id** · impact_pt_rs · impact_lo_rs · impact_hi_rs · horizon_days · owner_user_id · confidence · monitoring_metric · monitoring_cadence · monitoring_window_days · success_band_pct · constraints json (each check pass/fail) · **guardrail_refs[]** · **guardrail_status** (overall: PASS/WARNING/FAIL/UNKNOWN — worst of children per policy) · rights_verdict (AUTHORIZED/ESCALATE/BLOCKED) · escalation_to_user_id · evidence_set json · simulation_version · status (draft/simulated/guardrail_blocked/approvable/approved/rejected/overridden/monitoring/closed) · outcome_id.

**11. DecisionGuardrail** — `decision_guardrails`
id · decision_id · target_kpi_id · guardrail_kpi_id · threshold_type (min/max) · threshold_value · actual_value (current) · expected_value (projected) · status (PASS/WARNING/FAIL/UNKNOWN) · confidence · method · source_refs.

**12. DecisionImpact** — `decision_impacts`
id · decision_id · source_kpi_id · affected_kpi_id · effect_type (revenue/cost/availability/risk/…) · direct_or_secondary (direct/second_order) · estimated_effect · lower_bound · upper_bound · confidence · horizon · dependency_path (edge chain over kpi_relations) · method (graph_elasticity) · evidence_refs.

**13. DecisionCollision** — `decision_collisions`
id · portfolio_id · decision_a_id · decision_b_id · affected_kpi_id · combined_effect · severity (HIGH/MEDIUM/LOW) · explanation · resolution_options json · status (OPEN/RESOLVED/ESCALATED) · owner · timestamps.

**14. DecisionPortfolio** — `decision_portfolios`
id · tenant · scope (org/region) · active_decisions json (derived) · target_kpis json · combined_expected_impact (point + range, summed from stored impacts) · guardrail_summary (counts per status) · collision_summary · portfolio_risk · approval_summary · cost_of_waiting (max over active CRITICAL cases) · status · timestamps. **Rule:** every portfolio number derives from stored DecisionRecord/DecisionImpact/DecisionCollision artifacts — the portfolio never invents quantitative truth.

**15. ProposedContractChange** — `contract_change_proposals`
id · contract_id · contract_version (base) · change_type (driver_prior/threshold/driver_add/entitlement/rights/…) · current_value · proposed_value · reason · evidence_refs · feedback_refs · impact_assessment · proposer_user_id · reviewer_user_id · status (DRAFT/IN_REVIEW/APPROVED/MERGED/REJECTED) · timestamps · merged_version.

**16. FeedbackRecord** — `feedback_entries`
type (hypothesis_verdict/driver_correction/evidence_rating/recommendation_rating/override_reason/action_outcome) · target_id · value json · actor_user_id · version · effect json · proposal_id (when it triggers a contract change).

**17. HistoricalCase** — `historical_cases` (CHANGE: + embedding vector(pgvector), embedding_method, embedding_version)
kpi_id · movement summary · driver · evidence summary · decision · outcome · **embedding** · similarity_explanation template · tenant · entitlement scope.

**18. TransparencyRecord** — `stage_telemetry` (repurposed from `AgentRun`; extended)
run_id · stage_code · method_label · llm_used · **model_class · route_reason · provider** · latency_ms · tokens_in · tokens_out · cost_est · **cache_hit · cache_latency_saved_ms · cache_cost_avoided_rs** · confidence_impact · source_count · ok. Plus `model_route_log` (capability, data_classification, policy_ref, decided_class, decided_provider, reason_code, fallback_used) and `cache_log` aggregates (key_pattern, hits, misses, savings).

Supporting: `organizations`, `users`, `roles`, `source_systems`, `knowledge_entities`, `knowledge_relationships`, `simulation_results`, `decision_approvals`, `outcomes`, `pattern_reliability`, `ai_policy` (capability × data_classification × tenant → allowed model classes, providers, caps), `audit_events`, `idempotency_records`.

### D.2 Database architecture rules

- **Tenant scoping:** every tenant-owned row carries `organization_id`; the data-access layer injects the predicate on every query; cross-tenant IDs return 404.
- **Indexes (hot paths only):** `kpi_observations(kpi_id, period_key)` · `kpi_observations(source_id, period_key)` · `reconciliation_runs(contract_id, run_ts desc)` · `detection_results(kpi_id, timestamp desc)` · `materiality_scores(org_id, band)` · `evidence(investigation_id, state)` · `stage_telemetry(run_id, stage_code)` · `historical_cases(org_id)` + ivfflat index on the embedding column once the case store grows beyond prototype scale (brute-force cosine is fine for ~10² cases) · `decision_records(org_id, status)` · `decision_collisions(portfolio_id, status)`.
- **Versioning:** contracts (snapshot per edit) · contract change proposals (base version → merged version) · simulation results · decision records (version + expected_version optimistic concurrency → 409) · feedback (version per target) · embeddings (embedding_version).
- **Audit:** `audit_events` for login, contract edits, proposal reviews/merges, conflict resolutions, investigations, simulations, approvals, overrides, outcomes, feedback, masking events, rights denials, route policy denials, cache evictions, demo-control actions.
- **Workflow states:** `investigations.workflow_state` per Section Q; transitions are server-side rules.
- **Authorization:** entitlement resolution cached per (role, contract_version); applied at the data-access layer (row predicate) and serialization layer (column masking/domain) — never in the UI.
- **No unnecessary complexity:** no RLS, no CDC, no materialized views; portfolio aggregates computed on demand (≤ 150 ms target) and stored as snapshots.

---

# E. KPI CONTRACT ARCHITECTURE

- **API:** `POST /contracts` · `GET /contracts` · `GET/PATCH /contracts/{id}` · `GET /contracts/{id}/versions` · `GET /contracts/{id}/gaps` · **`GET /contracts/{id}/proposals`** (Section P).
- **Status machine:** DRAFT → ACTIVE → CONFLICTED (set by reconcile on a definition conflict) → UNDER_REVIEW → ACTIVE. Version increments on every change.
- **Gap report** (degrade loudly): no thresholds → materiality statistical-only; no drivers → hypothesis space shrinks to decomposition-derived drivers, confidence capped; no rights → no action recommendations, explicit banner; no owner → conflicts/clarifications unroutable → ABSTAIN reason "owner unassigned"; formula conflict → CONFLICTED; **no guardrail configuration → decision options downgrade to "no guardrail coverage" and approval requires escalation**.
- **Governed evolution (Section M.2):** the learning loop NEVER mutates an ACTIVE contract. Change proposals flow `LEARN → ProposedContractChange → Governance Review → APPROVE/REJECT → MERGE → new ACTIVE version`. Only the KPI owner or a designated governance role can merge; every merge carries actor + reason + evidence and is audited; every version remains auditable; investigations pin `contract_version` at investigation time.

---

# F. RECONCILIATION ARCHITECTURE

- **Flow:** `NORMALIZE → COMPARE → CLASSIFY → SCORE → ROUTE` per cycle (on source refresh and always before an investigation). Source sets come from the scenario configuration.
- **Normalize:** canonical entities (`entity_resolution.py`), calendar alignment (`calendar_rule`), unit/currency.
- **Compare:** same-meaning values across sources vs tolerance bands from contract data-quality rules.
- **Classify:** definition (same KPI, different formula/config across sources) · refresh (age beyond publish tolerance) · grain (aggregation mismatch) · hierarchy (unresolved entity) · calendar (period boundary) · coverage (missing rows) · entity (alias resolution failure).
- **Score (deterministic penalties):**

```
definition_conflict  0.12  (surfaced as "confidence impact −0.12")
stale_source         0.00 / 0.06 / 0.12 / 0.15  (≤2d beyond tolerance / 3–5d / 6–9d / ≥10d)
grain_mismatch       0.05
coverage_gap         0.10
hierarchy_unresolved 0.08
calendar_mismatch    0.05
reliability = clamp(1 − Σ penalties, 0.4, 1.0)
verdict: CONFLICTED if active definition conflict OR reliability < 0.75 · MINOR if any penalty · else CONSISTENT
confidence_cap = reliability + 0.10 (≤ 1.0)
hard rule: an active definition conflict caps certainty at ACT_WITH_CAUTION
```

- **Demo targets (locked):** NE case — definition conflict 0.12 + stale POS 0.12 → reliability **0.76**, cap 0.86, impact **−0.12** (matches the locked script: "ERP ₹84M vs Finance ₹87M · reliability 0.76 · confidence impact −0.12"). South case — stale POS 0.12 + grain 0.05 → reliability 0.83, cap 0.93.
- **Route:** definition → KPI owner (rights-checked resolution); refresh/coverage → data owner; grain → analyst note. Conflicts are never silently merged; the working value row carries its justification.

---

# G. MATERIALITY ENGINE

`detect` produces `DetectionResult` (significance only); `triage` produces `MaterialityAssessment` (business judgment). Two stages, two tables, two ledger rows. Weights (exposure per point, margin weight, strategic weight) come from the scenario-configured contract thresholds.

```
significance = clamp((max(robust_z, 6×anomaly_score) − 2) / 4, 0, 1)
impact = |deviation_rs| × exposure_per_point + margin_weight × |deviation_pct| + strategic_weight
score   = significance × clamp(log1p(impact)/10, 0, 1)
bands:  ≥ 0.70 CRITICAL · ≥ 0.40 ELEVATED · ≥ 0.15 WATCH · else NOISE
```

**Demo targets (locked):** Revenue NE −12% · 5.1σ · ₹8.6M exposure · strategic 0.8 → **CRITICAL**. Marketing ROI −4% · 2.1σ · ₹0.2M → **WATCH**. Every score stores its full arithmetic json for the "why is this CRITICAL?" drill-down.

---

# H. EXPLANATION / REASONING ARCHITECTURE

### H.1 The two-layer split (non-negotiable)

| | Quantitative truth layer | Generative layer |
|---|---|---|
| Methods | SQL · deterministic logic · statistics · ML · contribution analysis · graph checks · retrieval scoring · calibration | LLM: hypothesis drafting · evidence-text extraction · narrative translation |
| Constraint | Owns every number in the product | Owns zero numbers |
| Failure | Deterministic, reproducible, versioned | Optional, labeled, routed, metered, replaceable |

### H.2 Contribution analysis (quantitative spine)

```
Revenue Δ = price + volume + mix + region + residual
price   = Σ_sku (p1−p0)·q0      volume = Σ_sku (q1−q0)·p0
mix     = Σ_sku (p1−p0)·(q1−q0)  region = Σ_region ΔRevenue_region − (Σ_sku Δ over regions)
residual = ΔRevenue − (price+volume+mix+region)   (seasonal attribution via baseline comparison)
```

Supporting dimensions: SKU · region · channel · product · customer segment. Every component is a row with `method` and `query_ref`. **Demo targets:** price **+1.8%** · volume **−9.5%** · mix **−0.9%** · region +0.0% · residual **−3.4%**.

### H.3 Conceptual flow (numbered, auditable)

1. DETECT (stats; LLM no) → 2. DECOMPOSE (sql; LLM no) → 3. HYPOTHESIZE — scenario-configured drivers + graph neighborhood → k rival hypotheses (llm drafting, template fallback) → 4. GATHER — scoped retrieval + claim extraction (extraction labeled) → 5. SCORE — support vs contradiction, graph path existence, temporal alignment (ml+rules; LLM no) → 6. RANK & CALIBRATE — confidence composition with pattern priors (rules+stats; LLM no) → 7. CERTAINTY STATE (rules; LLM no) → 8. NARRATE — persona briefs rendered from the structured conclusion object (llm; numeric post-check enforced).

### H.4 Hypothesis scoring

```
balance = (support − 1.5×contradiction) / (support + contradiction + ε)
confidence = 0.35·balance + 0.20·freshness_avg + 0.15·source_agreement + 0.30·pattern_prior
final = confidence × confidence_cap
```

**Demo targets:** supplier delay **0.82** (→ ×0.86 cap = **0.71**) · competitor promo **0.12** · marketing **0.04** · seasonal **0.02**. NE lead margin 0.70. Scenario 2: transport delay 0.74 · demand surge 0.18 · quality returns 0.06 · seasonal 0.02.

### H.5 Evidence system

Chain: `Insight → EvidenceRecord → Source → timestamp → freshness → lineage → analytical method → data classification`. States: SUPPORTING / CONTRADICTING / STALE / RESTRICTED. Rules: no evidence without a source; no claim without evidence; every source openable; freshness affects scoring; restricted evidence counts as "n sources withheld" and lowers confidence; retrieval always scoped; **data classification bounds which model classes may process the text (Section O.2)**.

### H.6 LLM facade — exactly three capabilities (plus one metered utility)

| Capability | Stage | Contract | Fallback |
|---|---|---|---|
| `draft_hypotheses(drivers, movement, k)` | hypothesize | Output constrained to scenario/contract drivers + graph neighborhood | Config templates |
| `extract_claims(source_text, entities)` | gather | Returns claim + polarity + source spans; never KPI numbers | Rule/keyword extractors |
| `translate_narrative(conclusion_obj, persona)` | narrate | Must not alter numbers, ranks, certainty state — enforced by a **numeric post-check** | Template renderer |
| `embed_case(case_summary)` | learn (case closure) | Metered utility for memory vectors; hashing-vector fallback (Section N) | Feature-hashing embedding |

All four pass through the Model Routing Gateway (Section O.3). Any other code path calling a provider is a build failure (lint rule). `llm_enabled=false` flips everything to fallbacks mid-session. Cost caps per tenant degrade LLM stages to deterministic with a visible banner.

### H.7 Knowledge graph (engine-only)

`knowledge_entities` / `knowledge_relationships` power driver maps, reasoning paths (`Apex Supplier → DELAYED_BY → Guwahati DC → IMPACTS → OSA → IMPACTS → Revenue`), and — with the elasticity/lag attributes on `kpi_relations` — second-order impact propagation (Section K.3). **No standalone graph screen** — paths render inline as query-backed chains.

---

# I. CERTAINTY STATE MACHINE

Backend-controlled state; the confidence number is an input, not the answer.

```
ABSTAIN        if final_conf < 0.50 OR (top1 − top2) ≤ 0.05 OR contradiction ≥ support
               OR active contract conflict with unroutable owner OR permission-limited evidence
CLARIFY        if a named, resolvable gap exists with a routed owner AND final_conf < 0.70
ACT            if final_conf ≥ 0.70 AND (top1 − top2) ≥ 0.15 AND no active definition conflict
               AND all sources fresh AND history sufficient
ACT_WITH_CAUTION otherwise (and whenever an active definition conflict exists)
COLD START     (mode, not state) — history < min_history → certainty ≤ CLARIFY, confidence ≤ 0.45
```

| State | Downstream behavior |
|---|---|
| ACT | Full decision options, simulation, guardrail/impact/collision analysis, approval workflow |
| ACT_WITH_CAUTION | Wider impact ranges, mandatory monitoring plan, approval required regardless of amount |
| CLARIFY | Case parks; clarification request issued to routed owner; auto-resumes when the named data arrives |
| ABSTAIN | **No action options.** Six fields always shown: why it cannot conclude · what evidence conflicts · what information is missing · what would resolve it · who should provide it · whether waiting is safer |

**Demo targets:** NE case → final 0.71 but **ACT_WITH_CAUTION** (definition-conflict hard rule — strong evidence held back by an unresolved definition). South case → 0.47×0.93 = 0.44, lead 0.02 → **ABSTAIN**. Millet Noodles → COLD START (≤ CLARIFY, capped 0.45, monitor-only).

---

# J. PERSONA & ENTITLEMENT ARCHITECTURE

### J.1 Persona briefs — one conclusion object, four views

The pipeline stores ONE structured conclusion object (`explain_result` json: numbers, ranks, certainty, evidence ids). `services/persona.brief(role)` renders from it:

| Persona | Brief contents | Controls | Data visibility |
|---|---|---|---|
| EXECUTIVE | 5–7 lines: exposure, top driver, confidence, cost of waiting, decision required + portfolio context | Approve/decline escalated decisions; view portfolio | Aggregates; no PII; no cost columns |
| ANALYST | Method dossier: formulas, decomposition, evidence+contradictions, lineage, telemetry, routes | Challenge/correct (feedback → proposals); no approval | Detail within own scope; PII masked |
| SUPPLY_CHAIN | SKU/site playbook: operational driver, authorized action, owner, monitoring plan, guardrails | Simulate/approve within authority; escalate above | Own region rows; `unit_cost_rs`, `marketing_roi` masked |
| KPI OWNER | Contract health: conflicts, lineage, drivers, thresholds, rights, **change proposals** | Resolve conflicts; review/approve/reject/merge proposals | Contract + lineage scope |

**Invariant:** personas never receive different underlying truths — only depth, evidence visibility, narrative, action set, and controls differ. The numeric post-check (H.6) verifies narrative outputs against the conclusion object.

### J.2 Data-level entitlements (server-side only)

| Mechanism | Implementation | Demo case |
|---|---|---|
| Row-level | Mandatory predicate from `kpi_contract_entitlements.row_scope` injected at the data-access layer | SC Manager sees NE rows only |
| Column-level | Serialization masking from `masked_columns`; audited | `unit_cost_rs`, `marketing_roi`, PII masked |
| Domain-level | Route guards on module routers | GL-derived values restricted |
| Evidence access | `access_scope` on evidence; withheld evidence counted, not hidden | SC cannot open supplier-cost evidence |
| Scenario access | scenario entitlement config gates which personas see which scenario | Scenario 2 restricted to ops personas in demo |

---

# K. DECISION RECORD ARCHITECTURE (WITH GUARDRAILS, IMPACTS, COLLISION, PORTFOLIO)

### K.1 The extended Decision Record

`decision_records` implements the PS schema + extensions: **driver → controllable lever → action → expected impact (point + range, horizon) → owner → confidence → monitoring plan** + target KPI · constraints json (each check pass/fail) · **guardrail results + overall guardrail status** · rights verdict · escalation target · evidence set · simulation version · approval status · human decision · outcome · outcome variance · reliability update.

**Why it beats a generic recommendation:** it converts advice into an auditable, business-safe enterprise asset — who decided, on what evidence, against which guardrails, with what expected side-effects, and whether it worked.

### K.2 Guardrail KPIs

Evaluated **on the backend** during `guardrails_check`; the UI renders them, never computes them.

| Guardrail state | Meaning | Approval behavior |
|---|---|---|
| PASS | No projected breach | Approvable (subject to rights) |
| WARNING | Near or soft breach of a guardrail band | Proceeds **only with explicit monitoring**; monitoring plan mandatory; approval note recorded |
| FAIL | Projected breach of a hard guardrail threshold | **Action cannot be approved** — option status → `guardrail_blocked`; UI shows the failing guardrail + threshold + projection |
| UNKNOWN | Projection confidence too low or guardrail data missing | Clarification request, or cautious approval per scenario policy (default: treat as WARNING + escalation) |

**Hero-scenario guardrails (seeded, scenario-configured):** Gross Margin ≥ −1% · Inventory Cover ≥ 5 days · Cash Exposure ≤ ₹2M · Customer SLA ≥ 95%.
**Demo targets:** Option A (backup supplier): margin −0.4% PASS · cover +3.1d → 8.2d PASS · cash ₹1.6M ≤ ₹2M PASS · SLA 96.2% PASS → overall **PASS**. Option B (air freight): cash ₹3.4M → **FAIL** + margin −1.8% → **FAIL** → not approvable (+ rights ESCALATE). Option C (price promotion): cover −18% → below 5d → **WARNING/FAIL** + SLA 93% → **FAIL** (see the second-order comparison moment, §T step 6).

### K.3 Second-order impact analysis

`second_order_impact` propagates each option's direct effect through `kpi_relations` (elasticity, confidence, lag per edge):

```
for edge (source → affected) on path: effect = parent_effect × edge.elasticity (multiplicative damping)
confidence = Π edge_confidences × horizon_factor
bounds = estimate ± proportional spread (wider per hop)
dependency_path = edge chain (rendered as a clickable path, not a graph page)
method label: "graph_elasticity" (rules)
```

**Demo target (the memorable comparison):** Option C "Increase promotion 10%" → direct Revenue **+8%** → second-order Inventory **−18%** · stockout risk **+12 pts** · complaints **+7%** → guardrail breach (OSA/cover) → **NOT SAFE TO APPROVE**. Phased variant A' "Restore stock, then promote" → Revenue **+7%** (slower) · Inventory **+4%** → guardrails **PASS** → decision health **BETTER**. This is explainable decision comparison — never autonomous optimization; the human still approves.

### K.4 Decision collision detection

`collision_check` compares the option's `DecisionImpact` set against all active/proposed decisions in the portfolio: a collision exists when two decisions affect the same KPI with **opposing signs**, or amplify it beyond a guardrail threshold.

**Demo target:** D2 "Reduce procurement safety stock" (Procurement, PENDING; Inventory −15%) + D3 "Increase NE promotion" (Marketing, PENDING; Inventory −18%) → combined cover −3.9d → below the 5-day guardrail → **combined stockout risk +17 pts** → `DECISION COLLISION DETECTED` (severity HIGH, affected owners: Procurement, Marketing, Supply Chain). Resolution options shown (sequence D2 after recovery confirms · escalate combined approval to CFO · abandon D3); the system detects and surfaces — humans resolve. **Policy:** unresolved HIGH collision blocks approval until resolved; MEDIUM requires an acknowledgment note; LOW is informational.

### K.5 Decision Workspace — four layers

| Layer | Contents |
|---|---|
| 1 — Recommendation | driver → controllable lever → action |
| 2 — Direct Impact | target KPI, expected impact + range, cost, risk, recovery, time horizon |
| 3 — Guardrails | per-guardrail PASS/WARNING/FAIL/UNKNOWN panel with threshold vs projection |
| 4 — Second-Order / Collision | affected KPIs, dependency paths, secondary effects, active decision conflicts, portfolio impact |

**The decision cannot be approved if a hard guardrail FAILs or decision rights prohibit it.** Approval is always human (Section L).

### K.6 Decision Portfolio (lightweight aggregation)

The portfolio is a **decision-intelligence aggregation layer, not project management**. `GET /decisions/portfolio` derives from stored artifacts only: active decisions (driver, owner, target KPI, impact, guardrail status, collision status, approval status) · combined expected benefit (sum of stored impacts with signs; range = sum of bounds — honest arithmetic) · guardrail summary (counts) · unresolved collisions · decisions awaiting approval · highest cost of waiting · overall portfolio health:

```
health = 0.4·guardrail_pass_rate + 0.3·collision_free_rate + 0.3·approval_freshness
```

Aggregation runs on demand (target ≤ 150 ms) and snapshots to `decision_portfolios`. No new quantitative truth is ever invented at this layer.

---

# L. DECISION RIGHTS ARCHITECTURE

Real policy logic, not UI gating: `kpi_contract_rights(role, action_class, approve_limit_rs, escalate_to_role)` + scope constraints.

- `verdict(option, user) → AUTHORIZED | ESCALATE(approver) | BLOCKED(reason)` — computed server-side per option; the UI renders the verdict but cannot change it.
- Analyst: simulate + challenge + correct, **no approval** (403 enforced).
- SC Manager: approve ≤ ₹2M in own region; above → ESCALATE to CFO.
- Executive: approve escalated actions; overrides must record a reason (required field, feeds learning).
- **Belt and suspenders:** approval requires rights verdict AUTHORIZED **and** guardrail status ≠ FAIL **and** no unresolved HIGH collision. All three gates are server-side; all denials are audited.
- Rights are versioned with the contract; rights changes are ProposedContractChange-governed.

---

# M. LEARNING & FEEDBACK ARCHITECTURE (WITH GOVERNED CONTRACT EVOLUTION)

Two mechanisms, both transparent. **Not RLHF, not autonomous retraining** — empirical recalibration with visible effects, and contract evolution via governed merges.

### M.1 Outcome learning and structured feedback

**Outcome learning:** predicted vs actual → error, alignment, band check; reliability posterior = (hits + 10×0.5) / (n + 10) — shrunk toward a prior when n is small.
**Structured feedback** (`feedback_entries`):

| Type | Effect (stored in `effect json`, shown in UI) |
|---|---|
| hypothesis_verdict | pattern prior for the hypothesis class updates (visible: "prior 0.12 → 0.07") |
| driver_correction | decomposition weights corrected; contract driver **proposal** created |
| evidence_rating | retrieval scoring feature weights adjust (not model retraining) |
| recommendation_rating | decision template ordering |
| override_reason | required on override; stored with the decision |
| action_outcome | outcome record → reliability update |

### M.2 Governed contract evolution (ProposedContractChange)

**The learning loop NEVER directly mutates an ACTIVE contract.** Anything that would change a contract — outcome-derived threshold recommendations, analyst corrections, driver corrections, feedback-derived prior changes — produces a `ProposedContractChange` instead:

```
LEARN → ProposedContractChange (DRAFT) → Governance Review (IN_REVIEW)
      → APPROVED/REJECTED → MERGE → new ACTIVE contract version (audited)
```

- Only the KPI owner or a designated governance role can review/merge; merge records actor + reason + evidence + resulting version; every version remains auditable.
- Proposals carry: change_type, current_value, proposed_value, reason, evidence_refs, feedback_refs, impact_assessment, proposer, reviewer, status, timestamps, merged_version.
- Investigations pin `contract_version` at investigation time, so past conclusions remain reproducible under their governing definition.
- **Demo (extension beat 10b):** analyst marks "competitor promotion" incorrect → LEARN proposes pattern prior 0.12 → 0.07 → KPI owner sees what changed, why, and the expected effect → **Approve & Merge** → new ACTIVE contract version. Never automatic.

---

# N. INSTITUTIONAL MEMORY ARCHITECTURE (PGVECTOR)

**PostgreSQL 16 + pgvector — the same store, the same tenant/entitlement predicates.** No separate vector database.

- **Embeddings:** at case closure, `embed_case(case_summary)` (metered, routed, cached) produces the case vector; **deterministic fallback** = Round 1 feature-hashing embedding into the same column (labeled `embedding_method`, `embedding_version`), so deterministic mode keeps memory working.
- **Retrieval pipeline (in order):** 1. tenant + entitlement filtering (row scope) → 2. structured filters (KPI, driver, entity, region, action, outcome, time window) → 3. pgvector cosine similarity → 4. optional PostgreSQL full-text search (`tsvector`, plainly labeled — no BM25 claims) → 5. structured rerank (facet-match bonus) → 6. **written similarity explanation**: which entities matched · which KPI/driver matched · similarity score · historical outcome · the lesson carried forward.
- **Consumers:** similar-case retrieval ("NE Q3 2025, similarity 0.87, same supplier + same DC, outcome +₹3.1M within band") · sparse-history analogues · pattern reliability priors.
- **Fallback:** pgvector unavailable (e.g., SQLite test mode) → structured-filter + hashing-cosine path with a visible DEGRADED note (spec's degrade-loudly rule).
- **Demo target:** retrieval returns the NE Q3 2025 case at ≥ 0.85 with the written explanation.

---

# O. TRANSPARENCY, TELEMETRY & AI GOVERNANCE ARCHITECTURE

### O.1 Telemetry (real execution metadata only)

The pipeline runner writes one `stage_telemetry` row per stage per run (extended schema per D.18); persona briefs add one row per persona. The ledger shows per-stage method, LLM usage, **model class, route reason, provider, fallback**, latency, tokens, cost, **cache hit + savings**, confidence impact, source count. Cost model: small-model rates ₹0.004/1k input + ₹0.012/1k output; cache hits discount inputs 50%; offline estimation labeled "estimated" (tokens ≈ chars/4). Per-tenant daily cost caps degrade LLM stages to deterministic with a visible banner. **Computed claims only:** "100% of the numbers on this screen were computed without an LLM" is derived from rows — never hardcoded. Drift view: per-stage latency/cost trends over runs.

### O.2 Model / AI governance policy (server-side)

`ai_policy` table: (capability × data_classification × tenant) → allowed model classes, allowed providers, latency budget, cost budget, fallback rule. Data classification (PUBLIC/INTERNAL/SENSITIVE/RESTRICTED) lives on sources/evidence. **Example (demoed in the ledger):** supplier-cost email is SENSITIVE → external premium model **prohibited** → approved model class only; route log shows the policy reference and reason code (`POLICY_APPROVED_CLASS`). Connection enforced end-to-end: **Data Sensitivity → Model Policy → Routing → Telemetry.** Policy violations are denied at the gateway (never silently rerouted) and audited.

### O.3 Model Routing Gateway

Business modules never call providers directly — all model calls pass through the gateway. The gateway receives: capability · task complexity · input size · data classification · latency budget · cost budget · tenant policy; it selects a **model class + provider adapter + settings + fallback + cache behavior**, and returns a route record with reason. At minimum:

| Capability | Model class policy | Rationale |
|---|---|---|
| `extract_claims` | fast/low-cost class | structured extraction; high volume |
| `draft_hypotheses` | reasoning-capable class | open-ended, needs calibration |
| `translate_narrative` | quality-preferred class | judge-facing prose |
| `embed_case` | embedding class (fast) | one call per closed case |

No hardcoded commercial model names — capability-based policy with provider adapters per class. Fallback ladder: policy denial → deterministic fallback · provider error → retry once on another adapter in the same class → deterministic fallback. Every route is visible in telemetry: capability, model class/provider, latency, tokens, cost, fallback, route reason.

### O.4 Semantic cache (Redis, validity-aware)

Cache **only derived, replayable artifacts**: persona narratives, repeatable evidence summaries (where safe), deterministic derived artifacts (e.g., ledger aggregates). **Never cache:** unauthorized data, raw confidential source content without policy controls, or mutable decision state without version validation. Cache key:

```
sha256( tenant_id | contract_version | investigation_version | conclusion_hash |
        persona | prompt_version | model_route )
```

- Same conclusion + same persona + same model/prompt version → **hit**; changed conclusion or any version → **miss**.
- **Invalidation:** conclusion change · contract version change · persona change · prompt version change · model route change · evidence state change — implemented via version-tagged key patterns (evict `tenant|contract_ver|*` on version bump).
- **Tenant isolation is absolute** — tenant_id is in every key; cross-tenant reads are impossible by construction.
- **Telemetry:** `cache_hit` / `cache_miss` / `latency_saved` / `cost_avoided` in stage telemetry + aggregate endpoint (no separate cache-management API).
- **Degradation:** Redis absent ⇒ cache disabled (logged, audited) — never wrong, only slower/costlier.
- **Demo target:** CEO re-opens her brief (unchanged conclusion) → cache hit → "₹0.13 avoided, 620 ms saved" visible in the ledger.

---

# P. API ARCHITECTURE

Round 1 envelope kept: `{data, meta:{request_id,timestamp}, error:{code,message,details}}`. Base `/api/v1`. Auth: JWT + RBAC + tenant filter on every query.

### P.1 Core endpoints (existing, unchanged unless noted)

| Endpoint | Purpose | Permissions | Persistence effect |
|---|---|---|---|
| `POST /contracts` · `GET /contracts` · `GET/PATCH /contracts/{id}` · `GET /contracts/{id}/versions` · `GET /contracts/{id}/gaps` | Contract CRUD/versioning/gaps | ADMIN, KPI_OWNER (edits) | versioned snapshots |
| `POST /contracts/{id}/reconcile` · `GET /contracts/{id}/reconcile/latest` · `POST /conflicts/{id}/resolve` | Reconciliation | ANALYST/ADMIN run; routed owner resolves | runs + conflicts |
| `GET /queue` | Materiality queue | persona-scoped | — |
| `POST /investigations` · `POST /investigations/{id}/start` · `GET /investigations/{id}/explain` · `GET /investigations/{id}/certainty` | Investigation lifecycle | ANALYST/ADMIN start | pipeline run + artifacts |
| `GET /persona/{role}/brief/{investigation_id}` | Persona briefs | role match | cache entry |
| `POST /decisions/{id}/simulate` · `/approve` · `/override` · `/outcome` | Decision flow | rights-verified; 409 on stale version | versions + audit |
| `POST /feedback` | Structured feedback | ANALYST+ (type-gated) | feedback + recalibration (+ proposal) |
| `GET /memory/similar` | Case retrieval | entitlement-filtered | — |
| `GET /telemetry/runs/{run_id}` · `GET /transparency` | Ledger + caps + drift + routes + cache | scope-checked | — |
| `POST /demo/inject-pos` · `/fast-forward` · `/toggle-llm` · `/reset` | Demo controls | DEMO_MODE only | audited mutations |

### P.2 New endpoints (Improvements 1–5)

| Endpoint | Purpose | Request | Response | Permissions | Validation | Persistence | Audit |
|---|---|---|---|---|---|---|---|
| `GET /scenarios` | List scenario templates (industry, problem, KPIs, demo priority) | — | scenario cards | persona-scoped visibility | — | — | — |
| `GET /scenarios/{id}` | Full scenario config (sources, drivers, guardrails, dataset ref, ground-truth ref) | — | template + config | scope-checked | — | — | — |
| `POST /scenarios/{id}/start` | Provision/refresh scenario workspace + start its primary investigation | period, region | investigation id + workspace state | ANALYST/ADMIN | scenario ACTIVE; seed loaded | provisioning (idempotent) + new investigation | yes |
| `GET /decisions/portfolio` | Aggregated active decisions, combined impact, guardrail/collision/approval summaries, health | scope filter | portfolio snapshot | EXECUTIVE/ANALYST scoped | — | on-demand snapshot row | read-logged |
| `GET /decisions/portfolio/{id}` | Stored portfolio snapshot | — | snapshot | scoped | — | — | — |
| `GET /decisions/{id}/impacts` | Direct + second-order impact set with dependency paths | — | `DecisionImpact[]` | scoped | — | — | — |
| `GET /decisions/{id}/guardrails` | Per-guardrail status, threshold vs projection, method | — | `DecisionGuardrail[]` | scoped | — | — | — |
| `GET /decisions/collisions` | Active collisions across the portfolio | — | `DecisionCollision[]` | EXECUTIVE + affected owners | — | — | — |
| `POST /decisions/collisions/{id}/resolve` | Human resolution (sequence/escalate/abandon/acknowledge) | choice + note | updated collision | EXECUTIVE or affected owner | choice valid | status + resolution | yes |
| `GET /contracts/{id}/proposals` | List change proposals for a contract | — | proposals | scope-checked | — | — | — |
| `POST /contracts/{id}/proposals` | Create proposal (from feedback/learning) | change_type, proposed_value, reason | proposal DRAFT→IN_REVIEW | ANALYST+ | change_type valid | proposal row | yes |
| `POST /contract-proposals/{id}/approve` · `/reject` | Governance review | note | proposal state | KPI_OWNER / governance role | state machine | state change | yes |
| `POST /contract-proposals/{id}/merge` | Merge → new ACTIVE contract version | reason | new version id | KPI_OWNER / governance role | APPROVED state | version increment + snapshot | yes |
| `GET /ai/policy` | Effective policy matrix (capability × data_classification → classes/providers/caps) | — | policy rows | ADMIN, ANALYST | — | — | — |
| `GET /ai/routes/{run_id}` | Route log for a pipeline run (class, provider, reason, fallback, cost) | — | route rows | scope-checked | — | — | — |

Cache hit/miss and savings are exposed through existing telemetry endpoints (no separate cache-management API). All new endpoints follow the Round 1 envelope and tenant-isolation rules; all mutating endpoints write `audit_events`.

---

# Q. WORKFLOW ARCHITECTURE

`investigations.workflow_state` — server-side state machine:

```
CONTRACT_READY → RECONCILING → RECONCILED → DETECTING → DETECTED → TRIAGED
→ EXPLAINING → EXPLAINED → CERTAINTY_DECISION
     ├── CLARIFY            (paused; auto-resumes when the named data arrives)
     ├── ABSTAINED          (terminal; archived to memory with abstention record)
     └── DECISION_OPTIONS_GENERATED
           → SIMULATED
           → GUARDRAILS_CHECKED        (any option FAIL → that option BLOCKED)
           → SECOND_ORDER_ANALYZED
           → COLLISIONS_CHECKED        (unresolved HIGH ⇒ approval gate closed)
           → RIGHTS_CHECKED
           → DECISION_RECORD_CREATED   (only APPROVABLE options)
           → PORTFOLIO_UPDATED
           → HUMAN_APPROVAL → APPROVED | REJECTED | OVERRIDDEN
                 └─ APPROVED → MONITORING → OUTCOME_RECORDED → LEARNED (closed → memory + proposals)
ANY STATE → FAILED  (retryable from last-good artifact)
ALL_OPTIONS_BLOCKED → DECISION_BLOCKED  (replan: adjust assumptions and re-simulate)
```

- **Retries:** per-stage retry (2 attempts, backoff) for transient errors; then FAILED with last-good artifact and stage attribution.
- **Failure recovery:** re-`start` resumes from the last persisted artifact (checkpoint per stage); idempotency keys prevent duplicate runs.
- **Cancellation:** allowed until HUMAN_APPROVAL (user or admin); leaves audit trail.
- **Persistence:** every transition is a row (`investigation_stage_events`); browser refresh never loses state.
- **Exposure rule:** progress events are safe operational status only ("Guardrails checked", "Collision check complete"…) — **internal chain-of-thought is never exposed.**
- **Real-time UX:** SSE (`GET /investigations/{id}/events`) publishes: Reconciliation complete · Detection complete · Decomposition complete · Hypotheses generated · Evidence retrieved · Ranking complete · Certainty state determined · Decision options generated · Guardrails checked · Second-order analysis complete · Collision check complete · Decision record created · Portfolio updated. Redis pub/sub when available; in-process bus fallback.

---

# R. FRONTEND INFORMATION ARCHITECTURE

React 19 + Vite SPA, reusing Round 1's design system, `api.ts` client, and SSE plumbing.

| Route | Area | Primary persona | Key info / actions |
|---|---|---|---|
| `/scenarios` | Scenario Selector | All | Pick industry/business problem/KPI/region/period → loads the scenario's workspace; scenario cards show problem, KPIs, sources, demo priority |
| `/app` | Executive Overview | Executive | Materiality queue + **Decision Portfolio panel** (active decisions, combined impact, guardrail/collision summaries, health) |
| `/kpis` | KPI Intelligence | KPI owner | Contract portfolio with states (ACTIVE/CONFLICTED/COLD START), current values, open cases |
| `/kpis/:id` | **KPI Case File** (central experience) | All | Tabs: Contract (incl. **change proposals panel**) · Reconcile · Investigation · Decisions · History |
| `/decisions/portfolio` | Decision Portfolio | Executive, owners | Aggregated decisions, conflicts, approvals pending, cost of waiting, portfolio health |
| `/transparency` | Governance & Transparency | Analyst, exec | Ledger tables, **AI routing details (route reasons, policy, fallbacks)**, cache metrics, cost caps, drift |
| `/memory` | Institutional memory | All (scoped) | Similar cases with written similarity explanations |

**Panels (not standalone pages):** Decision Impact Map · Guardrail panel · Collision panel — inside the Decision Workspace; Contract Change Proposal panel — inside the Contract tab; AI routing details — inside the Transparency Ledger.

**DemoBar** (fixed, demo-mode only): persona switcher (EXEC / SC / ANALYST / KPI OWNER) · scenario switcher (S1/S2/S3) · `Inject POS refresh` · `Fast-forward 14 days` · `Toggle LLM` · `Reset`. All demo actions audit-logged.

**Persona rendering rule:** same components, different data — API returns persona-filtered payloads; the UI never re-implements entitlements, guardrails, or rights.

---

# S. SCREEN-BY-SCREEN PROTOTYPE SPECIFICATION

Compact format per screen: **Purpose · Persona · Layout · Data · Interactions · API · Backend · Loading · Empty · Error · Permission · Demo purpose.**

**S0 — Scenario Selector** · Purpose: prove engine generality; choose the business problem · Persona: ALL · Layout: scenario cards (industry, problem, primary KPI, related KPIs, sources, demo priority) · Data: `scenario_templates` · Interactions: select → workspace loads (contracts, queue, cases) · API: `GET /scenarios`, `GET /scenarios/{id}`, `POST /scenarios/{id}/start` · Backend: scenario provisioning (idempotent) + validation (every KPI has a contract; sources declared; guardrails exist; gaps listed loudly) · Loading: provisioning skeleton · Empty: n/a (3 seeded) · Error: scenario invalid → gap list, nothing half-provisioned · Permission: scenario entitlement config · Demo: step 1 + extension beat 13 (S2 switch).

**S1 — Executive Overview (+ portfolio panel)** · Purpose: the attention queue + decision portfolio · Persona: EXECUTIVE · Layout: 3-column materiality queue + "awaiting approval" strip + portfolio panel (active decisions, combined impact, guardrail counts, collision flags, health) · Data: materiality cards, portfolio snapshot · Interactions: open case file; approve/decline escalated decisions; drill collisions · API: `GET /queue`, `GET /decisions/portfolio`, `POST /decisions/{id}/approve` · Backend: triage aggregation + portfolio derivation (stored artifacts only) · Loading: skeleton queue · Empty: "No material movements — all KPIs within expected range" · Error: per-card retry, queue falls back to last persisted run · Permission: aggregates only; masked fields render as `—` · Demo: step 1.

**S2 — KPI Intelligence** · (unchanged from v2) portfolio of contracts with state chips; owner-only edit affordances · Demo: context for steps 2–9.

**S3 — KPI Case File** · (unchanged core) header (KPI, value, band, certainty chip) + 5 tabs · Backend aggregates across domain modules · Demo: spine of steps 2–7.

**S4 — KPI Contract tab (+ proposals panel)** · Purpose: governed definition + governed evolution · Layout: definition card; formula; owner; sources+lineage; drivers; thresholds; materiality rules; rights; entitlements; versions drawer; **change proposals panel** (proposal, reason, evidence, impact assessment, status, Approve/Reject/Merge for the owner) · Interactions: versioned edit (owner); review proposals · API: `GET/PATCH /contracts/{id}`, `/versions`, `GET /contracts/{id}/proposals`, `POST /contract-proposals/{id}/approve|reject|merge` · Backend: snapshot + audit on edit; proposal state machine server-side · Permission: proposals merge owner-only (analyst sees IN_REVIEW, cannot merge) · Demo: step 2 + extension beat 10b.

**S5 — Reconciliation tab** · (unchanged) verdict banner; conflict cards; freshness profile; working value · Demo: step 3 / **Moment 1**.

**S6 — Investigation tab** · (unchanged core) decomposition waterfall; hypothesis cards with support/contradict columns; reasoning path strip; confidence composition; certainty banner · Demo: step 4.

**S7 — Persona view (briefs)** · (unchanged) persona-specific brief card sets; numeric post-check enforced · Demo: step 5.

**S8 — Decision Workspace (four layers)** · Purpose: decide safely · Persona: SC, EXECUTIVE · Layout: option cards (driver→lever→action) → direct-impact panel → **guardrail panel** (per-guardrail status, threshold vs projection, method) → **second-order/collision panel** (affected KPIs, dependency paths, secondary effects, conflict flags, portfolio impact); sliders; simulation panel; approve bar · Interactions: slider → server simulation; compare options (the promotion vs restore-then-promote comparison); approve/override/reject · API: `POST /decisions/{id}/simulate`, `GET /decisions/{id}/guardrails`, `GET /decisions/{id}/impacts`, `GET /decisions/collisions`, `POST /decisions/{id}/approve|override|reject` · Backend: simulation + guardrails + impact propagation + collision check + rights — all server-side; approval gated by all three · Loading: simulation spinner with version note · Empty: ABSTAIN/CLARIFY → no options by design · Error: 409 stale version → re-simulate prompt · Permission: verdict enforced; analyst no approve button (403); FAIL/blocked options visibly disabled with reasons · Demo: step 6 (incl. the second-order comparison moment) + step 6b (collision).

**S9 — Abstention screen** · (unchanged) six fields, NO action buttons · Demo: step 8 / **Moment 2**.

**S10 — Sparse-history screen** · (unchanged) cold-start banner; analogues; wide CI; unlock conditions · Demo: step 9.

**S11 — Evidence & Lineage** · (unchanged + data classification chip per source, feeding the policy story) · Demo: steps 4, 10.

**S12 — Institutional Memory** · (updated) retrieval result cards with **written similarity explanation** (matched entities, KPI/driver match, score, outcome, lesson); embedding method label · API: `GET /memory/similar` · Backend: pgvector pipeline (N) with fallback · Empty: "No similar cases yet — this case will be the first" · Demo: step 11.

**S13 — Governance & Transparency (Ledger)** · (updated) per-stage method table; LLM/non-LLM split; latency/tokens/cost; **AI routing details** (capability → class/provider, route reason, policy ref, fallback); **cache metrics** (hits, latency saved, cost avoided); cost caps; drift chart · Backend: telemetry + route log + cache aggregates (real metadata only) · Demo: step 12 / **Moment 3**.

**S14 — Decision Portfolio** · Purpose: enterprise-wide decision context · Persona: EXECUTIVE, owners · Layout: active decision cards; combined-impact summary; guardrail/collision summaries; approvals pending; highest cost of waiting; portfolio health gauge · Data: portfolio snapshot (derived) · Interactions: open decisions; resolve collisions · API: `GET /decisions/portfolio`, `POST /decisions/collisions/{id}/resolve` · Loading: aggregation spinner · Empty: "No active decisions" · Error: fallback to per-decision listing · Permission: scope-filtered · Demo: step 6b.

---

# T. DEMO DATA ARCHITECTURE

### T.1 Scenario templates (three, one engine)

| Scenario | Business problem | Primary KPI | Related KPIs | Drivers (configured) | Evidence pattern | Actions | Guardrails | Demo role |
|---|---|---|---|---|---|---|---|---|
| **S1 — Revenue Decline (hero)** | NE revenue collapse | Revenue NE | OSA NE · Inventory cover NE · Marketing ROI · Supplier Reliability | supplier delay · competitor promo · marketing underperformance · seasonality | supplier email, WMS snapshot, POS audit, campaign report, market tracker, accrual note | backup supplier · air freight · price promotion (+ phased variant) | margin ≥ −1% · cover ≥ 5d · cash ≤ ₹2M · SLA ≥ 95% | **12-step hero** |
| **S2 — Inventory / Availability** | Cover collapse at a DC | Inventory days-of-cover NE | OSA NE · Revenue NE · Freight cost | transport delay · demand surge (monsoon) · quality returns · supplier dip | logistics emails, demand-forecast notes, quality reports, WMS snapshots | shift to alternate DC · selective air freight · expedite supplier | revenue ≥ −2% · margin ≥ −1% · SLA ≥ 95% | **Extension beat 13 (~3 min)** |
| **S3 — New Product / Sparse History** | Launch KPI with 5 weeks of data | Millet Noodles revenue | category analogues | cold-start mode | sibling launch histories, benchmark bands | monitor-only (until unlock) | margin ≥ −3% | step 9 (cold-start) |

Same pipeline for all three: `Scenario → KPI Contract → Reconcile → Detect → Triage → Explain → Decide → Learn`. Scenario configuration changes data, drivers, thresholds, actions, constraints, guardrails, personas — never the engine. AC18 proves it headlessly.

### T.2 Apex Foods data fabric (hero)

**Sources (5 simulated, deliberate heterogeneity):**

| Source | Kind | Cadence | Grain | Demo role |
|---|---|---|---|---|
| `erp` | ERP | daily | SKU×DC | Revenue invoiced ₹84.0M; price list; campaign spend |
| `gl` | Finance close | monthly | company×account | Revenue recognized ₹87.0M → **definition conflict** |
| `pos` | Retail audit | weekly | region×category | OSA NE 71%↓; South case; **6-day stale** |
| `wms` | WMS | daily | SKU×DC | Days-of-cover collapse at Guwahati DC |
| `scorecard` | Supplier scorecard | weekly | supplier×region | Supplier Reliability drop (supplier-hypothesis evidence) |

**KPIs (5 connected):** Revenue NE · OSA NE · Inventory days-of-cover NE (PRECEDES/IMPACTS edges with elasticity/lag for second-order propagation) · Marketing ROI · Supplier Reliability.

**Planted events:** supplier delay weeks 10–13 → cover ↓ → OSA NE ↓ → Revenue NE ↓; price +6% at week 10 (masks volume decline; drives decomposition); competitor promo weeks 12–14 in **South only** (NE red herring); marketing spend within plan (contradicts marketing hypothesis); returns-accrual note (explains ERP/GL gap).

**Evidence documents (seeded, with polarities, freshness, lineage, data classification):** supplier delay email (SENSITIVE — drives the routing-policy moment) · WMS Guwahati snapshot · POS audit report · campaign report ("within plan") · market tracker (promo in South, not NE) · finance accrual note · 3 sibling-SKU launch histories (cold-start analogues).

**Seeded decisions for the portfolio/collision beat:** D1 "activate backup supplier" (SC, APPROVED, monitoring) · D2 "reduce procurement safety stock" (Procurement, PENDING; inventory −15%) · D3 "increase NE promotion" (Marketing, PENDING; inventory −18%). D2+D3 → combined cover −3.9d → stockout risk +17 pts → **DECISION COLLISION** (HIGH).

**Scenario ledger** (`data/scenario_ledger_v2.json`): per investigation — planted driver, planted contributions, expected certainty, expected decision targets, expected guardrail states, expected collision. The E2E test asserts against it.

### T.3 Demo steps (hero = 12 core; extensions time-boxed)

| Step | Beat | Screen | What is proven |
|---|---|---|---|
| 1 | Scenario Selector + materiality queue | S0 + S1 | Generality claim opens the demo; Revenue NE CRITICAL vs Marketing ROI WATCH; Millet Noodles COLD START |
| 2 | Contract tab (+ proposals panel visible) | S4 | Governance before reasoning; versioned contract |
| 3 | **MOMENT 1 — Reconcile** | S5 | "Your inputs disagree": ERP ₹84.0M vs GL ₹87.0M, typed, capped (0.76/−0.12), routed |
| 4 | Investigation: decomposition + 4 hypotheses + evidence columns | S6 | price +1.8 / volume −9.5 / mix −0.9 / residual −3.4; hypotheses 0.82/0.12/0.04/0.02 |
| 5 | Persona switch (same case, 4 briefs, masked data) | S7 | Persona changes the answer/action; entitlements visible |
| 6 | Decision Workspace — 4 layers | S8 | Option A guardrails PASS, authorized; Option B cash FAIL + escalate; **second-order comparison**: promotion (+8% revenue, −18% inventory, OSA breached → NOT SAFE) vs restore-then-promote (+7%, +4%, PASS → BETTER); approve A |
| 6b | Decision Portfolio + **COLLISION** | S14 | D2+D3 collide on inventory (combined stockout risk +17 pts) → DETECTED, owners named, resolution options; human resolves |
| 7 | Outcome fast-forward | S3 History | +₹3.9M vs +₹4.1M within band; reliability updated (shrunk) |
| 8 | **MOMENT 2 — Abstention** | S9 | South case: DO NOT ACT YET + 6 fields |
| 9 | Sparse history (Scenario 3 config) | S10 | Cold-start mode: analogues, cap 0.45, monitor-only, unlock conditions |
| 10 | Feedback → proposal | S11/S4 | Analyst marks competitor-promo incorrect → pattern prior proposal |
| 10b | **Contract merge** (extension) | S4 | Proposal IN_REVIEW → KPI owner **Approve & Merge** → new ACTIVE version (never automatic) |
| 11 | Memory | S12 | pgvector retrieval: NE Q3 2025, similarity 0.87, written explanation |
| 12 | **MOMENT 3 — Transparency Ledger** | S13 | 2-of-7 stages LLM; **routing detail** (extract→fast, hypotheses→reasoning, narrative→quality; SENSITIVE evidence → approved-class-only route with reason); **cache hit** on the CEO brief (₹0.13 avoided); ~1,400 tokens; ≈ ₹0.19/insight |
| 13 | **Scenario 2 switch** (extension, ~3 min) | S0→S6 | Same engine, new problem: inventory scenario runs the identical pipeline (different drivers, evidence, actions, guardrails) — AC18 made visible |

**Demo targets (locked, asserted by the E2E test):** reliability 0.76 / impact −0.12 · CRITICAL vs WATCH · decomposition +1.8/−9.5/−0.9/0.0/−3.4 · hypotheses 0.82/0.12/0.04/0.02 · NE state ACT_WITH_CAUTION (0.71) · Action A ₹1.6M AUTHORIZED + guardrails PASS; B ₹3.4M ESCALATE + FAIL; promotion comparison NOT SAFE vs BETTER · collision +17 pts HIGH · outcome +₹3.9M vs +₹4.1M within band · cold-start cap 0.45 · memory 0.87 · ledger 2-of-7 LLM, ~1,400 tokens, ≈ ₹0.19 · cache hit shown · route reasons shown.

---

# U. SECURITY ARCHITECTURE

| Control | Implementation | Demo evidence |
|---|---|---|
| Authentication | JWT access + rotating refresh (PBKDF2, 210k iterations) | pre-provisioned personas sign in instantly |
| Tenant isolation | mandatory `organization_id` predicate; cross-tenant → 404 | security test suite |
| Role permissions | RBAC map (Round 1 extended) | analyst approve → 403 |
| Row-level access | entitlement predicates from contracts | SC sees NE rows only |
| Column-level masking | serialization layer; audited | `unit_cost_rs`, PII masked |
| Domain-level access | module route guards | GL values restricted |
| Source/evidence access | `access_scope` + withheld-count honesty | restricted evidence counted |
| **Data classification × model policy** | `data_classification` on sources/evidence → `ai_policy` → gateway enforcement (denials audited) | SENSITIVE supplier-cost evidence → approved-class-only route, reason shown |
| **Governed contract merges** | proposals + owner-only merge + audit | merge beat 10b |
| Audit trail | `audit_events`: login, edits, proposals, merges, conflicts, investigations, simulations, approvals, overrides, outcomes, feedback, masking, rights denials, route-policy denials, cache evictions, demo actions | audit tab |
| Data protection | PII classification at ingestion; retention config; parameterized SQL; security headers | PII masking demo |
| LLM governance | only the 3-capability facade + gateway; inputs/outputs logged; prompt versions pinned; cache never cross-tenant | ledger + route log |

**Everything server-side; the frontend is never the security boundary.**

---

# V. TESTING STRATEGY

**Unit tests** — KPI formulas & contract versioning · scenario template loading/validation · reconciliation penalty math & conflict typing · baseline/robust-z/anomaly · materiality bands · decomposition identities · hypothesis scoring & contradiction penalty · certainty state machine · simulation equations + constraint checks · **guardrail evaluation (all four states, thresholds vs projections)** · **impact propagation (elasticity chains, confidence decay, dependency paths)** · **collision detection (opposing signs, amplification, severity)** · **portfolio aggregation (sums match stored artifacts; range arithmetic)** · decision rights verdicts · **proposal state machine (authorization: analyst cannot merge; owner can; version increments; audit)** · shrinkage math · cost model.

**Integration tests** — investigation flow end-to-end · evidence retrieval with scoping · persona rendering (one conclusion object, four views) · decision approval chain (simulate → guardrails → impacts → collisions → rights → approve → audit) · outcome recording + reliability update · **memory retrieval (pgvector path + hashing fallback parity)** · feedback → proposal → merge · SSE progress events · **scenario switch: S1 and S2 run the identical pipeline code path with different configs (AC18)**.

**Security tests** — tenant isolation · role restrictions · row-level scoping · masked columns · restricted evidence counting · rights-denial audit rows · **routing policy: SENSITIVE evidence denied to disallowed class (audited); policy denial → deterministic fallback** · **cache tenant isolation (key construction test) + invalidation on contract-version bump** · merge authorization.

**End-to-end test** — `test_demo_scenario.py` runs the **full 12-step Apex Foods scenario headlessly** (including DemoBar actions: inject-POS, fast-forward, toggle-LLM, scenario switch) and asserts every locked demo target + the scenario ledger. The demo *is* a test; CI green = demo green.

**Acceptance-criteria mapping:**

| AC | Criterion | Test |
|---|---|---|
| AC#1 | KPI governed before reasoning | contract tests + E2E step 2 |
| AC#2–3 | Heterogeneous disagreement detected; conflict typed + capped | reconcile tests + E2E step 3 |
| AC#4 | Materiality calculated | triage tests + E2E step 1 |
| AC#5–7 | Quantitative reasoning without LLM; competing hypotheses; support/contradict evidence | explain tests + E2E step 4 |
| AC#8 | System can abstain | certainty tests + E2E step 8 |
| AC#9–10 | Persona changes answer/action; rights matter | persona/rights tests + E2E steps 5–6 |
| AC#11–13 | Structured action; interactive simulation; human approves | decide tests + E2E step 6 |
| AC#14–16 | Outcome recorded; feedback captured; memory retrieves | learn tests + E2E steps 7, 10, 11 |
| AC#17 | Telemetry visible | telemetry tests + E2E step 12 |
| **AC#18** | Same engine supports multiple business scenarios without separate implementation paths | scenario tests + E2E step 13 |
| **AC#19** | Decision is evaluated against guardrails | guardrail unit/integration tests + E2E step 6 |
| **AC#20** | Second-order impacts are surfaced | impact tests + E2E step 6 (comparison moment) |
| **AC#21** | Decision collisions are detected | collision tests + E2E step 6b |
| **AC#22** | Decision Portfolio aggregates active decisions and risks | portfolio tests + E2E step 6b |
| **AC#23** | Active KPI Contract evolves only through governed proposal → review → merge | governance tests + E2E step 10b |
| **AC#24** | LLM routing is task-aware, policy-aware, cost-aware, observable | routing/policy tests + E2E step 12 |
| **AC#25** | Memory uses pgvector with entitlement-aware retrieval | memory tests + E2E step 11 |
| **AC#26** | Semantic cache avoids repeated equivalent LLM work without violating version/persona/tenant boundaries | cache tests + E2E step 12 |

---

# W. PERFORMANCE / COST STRATEGY

**Targets (measured by telemetry + smoke script — never claimed until measured):**

| Metric | Target | Measurement |
|---|---|---|
| API read latency (p95) | < 300 ms | smoke script over `/queue`, `/explain`, `/transparency` |
| Investigation end-to-end | < 5 s offline · < 15 s with LLM | pipeline run totals |
| SSE first progress event | < 2 s | runner instrumentation |
| DB query latency (p95) | < 50 ms | SQLAlchemy event hooks in dev |
| Guardrail evaluation (per option) | < 50 ms | stage telemetry |
| Impact propagation (per option) | < 200 ms | stage telemetry |
| Portfolio aggregation | < 150 ms | portfolio endpoint |
| Memory retrieval (pgvector, ~10² cases) | < 300 ms | memory endpoint |
| Cache hit latency (p50) | < 10 ms | cache log |
| Model calls per insight | 2 (LLM stages) + ≤ 1 embed | ledger |
| Token usage per insight | ~1,400 | ledger |
| Cost per insight | ≈ ₹0.19 (±30%) | cost model over real tokens |
| Cache hit rate (repeated persona views) | ≥ 30% | cache aggregates |

**Extended telemetry:** LLM routing (selected model class/provider, route reason, fallback, cost) · semantic cache (hit rate, latency saved, cost avoided) · portfolio aggregation latency · impact dependency-calculation latency. **Cost controls:** per-tenant daily caps → deterministic degradation with banner; capability-based routing (fast class for extraction); semantic cache for repeats; offline mode as a first-class demo feature.

---

# X. DEPLOYMENT / LOCAL RUN STRATEGY

**Single Docker Compose file:** `api` (FastAPI + SPA static build) · `db` (**Postgres 16 + pgvector extension enabled at init**) · `redis` (semantic cache + rate limits + SSE; if absent → cache disabled + in-process fallbacks, logged). Same code falls back to SQLite for tests/offline (hashing-vector memory path).

**Local run:** `docker compose up --build` → seed runs idempotently on first boot (three scenario templates + Apex Foods fabric) → open `http://localhost:8000` → sign in as any seeded persona (`priya.ceo`, `rahul.sc`, `meera.analyst`, `vikram.owner`) → `DEMO_MODE=1`.

**Environment:** `DATABASE_URL` · `REDIS_URL` (optional) · `APP_SECRET_KEY` · `OPENAI_API_KEY` (optional — absent ⇒ deterministic mode, shown in UI) · `EMBEDDING_API_KEY` (optional — absent ⇒ hashing fallback) · `DEMO_MODE` · cost-model constants · policy table seeded via migration. `GET /api/v1/health/ready` reports `postgres: ok · pgvector: ok|degraded · redis: ok|degraded · llm: ok|deterministic`.

**Deterministic replay:** with LLM keys unset, `POST /investigations/{id}/start` produces bit-identical artifacts for identical seeds — demonstrated live (Toggle LLM) and asserted in CI.

---

# Y. IMPLEMENTATION ROADMAP (12 VERTICAL SLICES)

Each slice: backend · database · API · frontend · tests · demo value · dependencies. ~17 developer-days solo; ~9 with two developers. Priorities: **P0 (must work):** KPI Contract · Reconciliation · Materiality · deterministic reasoning · evidence · abstention · personas · entitlements · Decision Record · decision rights · simulation · basic guardrails · hero scenario · telemetry · security · deterministic fallback. **P1 (major differentiators):** scenario configuration · second-order impact · decision collision · Decision Portfolio · contract merge requests · model routing gateway · pgvector memory · semantic cache. **P2 (if time remains):** Decision TTL · Decision Debt · Semantic Drift · Pre-mortem · advanced multi-objective optimization. **P3 (do NOT build):** autonomous execution · autonomous enterprise optimizer · live ERP connectors · external social/news feeds · chatbot · NL-to-SQL · separate vector DB · separate workflow platform · graph visualization page · collaboration suite · billing/SSO · fine-tuning. **P1 must never block the P0 hero demo.**

| Slice | Contents | Tests | Demo value | Depends |
|---|---|---|---|---|
| **S1 — KPI Contract + Scenario Configuration + Case File** | contracts domain (fields, versions, status, gaps) · ScenarioTemplate model + validation + S1 hero config · `/contracts`, `/scenarios` APIs · Case File shell + Contract tab | AC#1 + contract/scenario units | Steps 1–2: governance-before-reasoning; generality visible | M0 foundation |
| **S2 — Reconciliation + Materiality** | reconcile domain · triage domain · `/reconcile`, `/queue` APIs · Reconcile tab + Overview queue | AC#2–4 | Steps 1 + 3 (**Moment 1**) | S1 |
| **S3 — Deterministic Driver Analysis** | detect reuse · decomposition SQL · decompose stage · Investigation tab waterfall | AC#5 + decomposition units | Step 4 spine (numbers without LLM) | S2 |
| **S4 — Evidence + Hypothesis Reasoning** | hypothesize + gather + score · evidence tables/states/classification · hypothesis cards · reasoning paths | AC#6–7 | Step 4 full | S3 |
| **S5 — Certainty / Abstention** | certainty stage + state machine · abstention screen (6 fields) · workflow states | AC#8 + state-machine units | Step 8 (**Moment 2**) | S4 |
| **S6 — Persona + Entitlements** | persona service + post-check · entitlements at query/serialization · DemoBar persona switch | AC#9 + security suite | Step 5 | S4 |
| **S7 — Decision Record + Simulation + Guardrails** | decision records (extended schema) · rights verdicts · simulation + constraints · **guardrail evaluation + BLOCKED status** · Decision Workspace layers 1–3 | AC#10–13, **AC#19** | Step 6 core (rights + guardrails in action) | S5–S6 |
| **S8 — Second-Order Impact + Collision + Decision Portfolio** | impact propagation over kpi_relations · collision detection · portfolio aggregation · Workspace layer 4 + portfolio panel + collision panel | **AC#20–22** | Step 6 comparison moment + 6b collision/portfolio | S7 |
| **S9 — Outcome + Feedback + Contract Proposals + Memory** | outcomes + shrinkage · feedback + pattern priors · **ProposedContractChange workflow** · case closure + **pgvector embeddings (+ hashing fallback)** · History tab + Memory screen + proposals panel | AC#14–16, **AC#23, AC#25** | Steps 7, 10, 10b, 11 | S8 |
| **S10 — Model Routing + AI Governance + Semantic Cache** | gateway + policy engine + route log · data classification plumbing · **semantic cache (validity-aware keys, invalidation, tenant isolation)** | **AC#24, AC#26** + security additions | Step 12 routing/cache moments | S9 |
| **S11 — Transparency Ledger + Scenario Switching** | telemetry capture + cost model + caps · ledger UI (routes + cache views) · drift · **scenario switcher UX + S2/S3 configs finalized** | AC#17 + scenario E2E | Step 12 (**Moment 3**) + step 13 | all |
| **S12 — Demo Polish + Full E2E Testing** | DemoBar actions (inject/fast-forward/toggle/scenario-switch/reset) · seed tuning to locked targets · full 12-step + extension E2E test · judge-script QA (offline + LLM) | full scenario test (AC#1–26) | the demo, twice without reset | all |

---

# Z. ROUND 2 REQUIREMENT TRACEABILITY MATRIX

`Requirement → Capability → Component → DB/Object → API → UI → Demo Step → Test`
Legend — Components: dS=domains/scenarios · dC=domains/contracts · dR=domains/reconcile · dD=domains/detect · dT=domains/triage · dX=domains/explain · dK=domains/decide · dP=domains/decision_portfolio · dL=domains/learn · sG=services/governance · sP=services/pipeline · sL=services/llm · sC=services/cache · sE=services/entitlements · sQ=services/persona · sT=services/telemetry.

| Official requirement | Capability | Component | DB/Object | API | UI | Demo | Test |
|---|---|---|---|---|---|---|---|
| Obj 1 — Detect & prioritise material movements | Detection + Materiality | dD, dT | detection_results, materiality_scores | `/investigations`, `/queue` | Overview queue | 1 | AC#4 |
| Obj 2 — Reconcile heterogeneous sources | Reconciliation Intelligence | dR, sE | reconciliation_runs/conflicts | `/reconcile`, `/conflicts/{id}/resolve` | Reconcile tab | 3 | AC#2–3 |
| Obj 3 — Rank explanatory drivers, appropriate methods | Explain engine | dX, sP | decompositions, hypotheses, evidence, pattern_reliability | `/explain` | Investigation tab | 4 | AC#5–7 |
| Obj 4 — Persona narratives, traceable evidence | Persona Intelligence | sQ, sL | explain_result, persona briefs, evidence | `/persona/{role}/brief` | Persona views | 5 | AC#9 |
| Obj 5 — Uncertainty + abstention | Certainty state machine | dX | certainty_states | `/certainty` | Abstention screen | 8 | AC#8 |
| Obj 6 — Actions grounded in levers/constraints/rights | Decision Record + Rights + **Guardrails** | dK, sE | decision_records, kpi_contract_rights, decision_guardrails | `/decisions/*`, `/decisions/{id}/guardrails` | Decision Workspace layers 1–3 | 6 | AC#10–13, AC#19 |
| Obj 7 — Learn from analyst/business feedback | Feedback + calibration + **governed contract evolution** | dL, sG | feedback_entries, pattern_reliability, outcomes, contract_change_proposals | `/feedback`, `/decisions/{id}/outcome`, `/contract-proposals/*` | History, dossier, proposals panel | 7, 10, 10b | AC#14–16, AC#23 |
| Obj 8 — Security, cost, latency, scalability | Entitlements + telemetry + **routing policy + cache** + scenario config | sE, sT, sP, sL, sC, dS | entitlements, stage_telemetry, ai_policy, cache metrics, scenario_templates | `/telemetry/*`, `/ai/*`, `/scenarios` | Transparency, masked views, Scenario Selector | 5, 12, 13 | AC#17, AC#24, AC#26, security suite |
| Core rule — LLM ≠ quantitative truth | Two-layer split + labeled, routed stages | sP, sL | stage_telemetry (method_label, llm_used, model_class, route_reason) | `/telemetry/runs/{id}`, `/ai/routes/{run_id}` | Ledger | 12 | AC#5, 17, 24 |
| Complexity — interacting drivers | Contribution analysis | dX | contribution_decompositions | `/explain` | Waterfall | 4 | decompose units |
| Complexity — cadence/grain/quality/coverage | Reconciliation penalties | dR | reconciliation_conflicts | `/reconcile` | Freshness profile | 3 | AC#2–3 |
| Complexity — inconsistent definitions/calendars | Conflict typing + contract status | dR, dC | kpi_contracts.status, conflicts | `/conflicts/{id}/resolve` | Conflict cards | 2–3 | contract/reconcile units |
| Complexity — sparse history | Cold-start mode | dD, dX | thresholds.min_history, cold_start_flag | `/explain` | Sparse-history screen | 9 | cold-start tests |
| Complexity — materiality = significance × impact | Materiality scoring | dT | materiality_scores.arithmetic | `/queue` | "Why CRITICAL?" drill-down | 1 | AC#4 |
| Complexity — contradictory evidence & calibration | Contradiction scoring + shrinkage | dX, dL | evidence.state, pattern_reliability | `/explain`, `/feedback` | Contradict columns | 4, 8, 10 | AC#6–8, 15 |
| Complexity — role-based personalization | Persona briefs | sQ | persona briefs | `/persona/{role}/brief` | DemoBar switch | 5 | AC#9 |
| Complexity — row/column/domain security | Data-level entitlements | sE | kpi_contract_entitlements | all (serialization) | masked views | 5 | security suite |
| Complexity — drift, feedback, continuous eval | Telemetry trends + recalibration | sT, dL | stage_telemetry, feedback | `/transparency` | Drift chart | 10, 12 | AC#15, 17 |
| Complexity — LLM economics | Cost model + caps + **routing + semantic cache** | sT, sL, sC | stage_telemetry.cost_est, ai_policy, cache metrics | `/transparency` | Ledger + cap banner | 12 | AC#17, 24, 26 |
| **Generality across business problems** | **Scenario configuration** | **dS** | **scenario_templates** | **`/scenarios`** | **Scenario Selector** | **1, 13** | **AC#18** |
| **Enterprise-wide decision context** | **Decision Portfolio** | **dP** | **decision_portfolios** | **`/decisions/portfolio`** | **Portfolio panel/view** | **6b** | **AC#22** |
| **Side-effects of actions (second-order)** | **Second-order impact analysis** | **dK** | **decision_impacts** | **`/decisions/{id}/impacts`** | **Impact map (Workspace L4)** | **6** | **AC#20** |
| **Conflicting concurrent decisions** | **Decision collision detection** | **dP, dK** | **decision_collisions** | **`/decisions/collisions`** | **Collision panel** | **6b** | **AC#21** |
| **Sensitive-data protection in AI processing** | **Model policy (classification × capability)** | **sL** | **ai_policy, data_classification** | **`/ai/policy`** | **Ledger routing view** | **12** | **AC#24 + security suite** |
| **Memory/retrieval with explainability** | **pgvector memory + written explanations** | **dL** | **historical_cases.embedding** | **`/memory/similar`** | **Memory screen** | **11** | **AC#25** |
| **Cost-efficient repeat insights** | **Semantic cache** | **sC** | **cache metrics in stage_telemetry** | **telemetry endpoints** | **Ledger cache view** | **12** | **AC#26** |
| Min — 3–5 connected KPIs, 2–3 sources, grains/cadences | Demo fabric (5 KPIs, 5 sources) | seed/fabric | kpi_observations, source_systems | all | whole app | 1–12 | E2E |
| Min — KPI/semantic contract | KPI Contract | dC | kpi_contracts + satellites | `/contracts/*` | Contract tab | 2 | AC#1 |
| Min — ≥2 personas | Persona Intelligence | sQ | persona briefs | `/persona/{role}/brief` | 4 personas | 5 | AC#9 |
| Min — multi-factor movement, known drivers | Planted ground truth + decomposition | seed/ledger, dX | scenario_ledger, decompositions | `/explain` | Waterfall + hypotheses | 4 | E2E vs ledger |
| Min — low-confidence: clarify/abstain | Certainty machine | dX | certainty_states | `/certainty` | Abstention screen | 8 | AC#8 |
| Min — sparse-history/new KPI | Cold-start mode | dD, dX | cold_start_flag, analogues | `/explain` | Sparse-history screen | 9 | cold-start tests |
| Min — role-based security scenario | Entitlements | sE | entitlements, audit | all | masked views | 5 | security suite |
| Min — evidence: freshness, method, contribution, confidence, lineage | Evidence chain | dX | evidence, evidence_sources | `/explain` | Evidence & Lineage | 4, 11 | AC#6–7 |
| Min — LLM vs non-LLM breakdown | Transparency Ledger | sP, sT | stage_telemetry | `/telemetry/runs/{id}` | Ledger | 12 | AC#17 |
| Min — runtime telemetry (latency, calls, tokens, cost) | Stage telemetry | sP, sT | stage_telemetry | `/telemetry/*` | Ledger | 12 | AC#17 |

---

# FINAL JUDGE VALIDATION

**Can a judge understand the product in 60 seconds?** Yes — "BI ends at insight, ERP begins at execution, ReasonFlow owns the governed middle" + the KPI Case File with its five tabs *is* the product, visible in the first minute.

**Can a judge verify the product in 5 minutes?** Yes — steps 1–4 (scenario selector → queue → contract → reconciliation conflict → decomposition + hypotheses) prove the core mechanism; everything else is depth on the same case file.

**Can the prototype demonstrate every Round 2 minimum requirement?** Yes — Section Z maps every requirement to a demo step and a test; the E2E test asserts all of them headlessly.

**Can a judge clearly distinguish ReasonFlow from Power BI + Copilot?** Yes — Copilot cannot show a KPI contract with rights, cannot stop at "your inputs disagree," cannot abstain, cannot gate an action by guardrails *and* rights, cannot show second-order side-effects or decision collisions, cannot show a governed contract merge or a decision portfolio. Steps 2, 3, 6, 6b, 10b demonstrate each absence explicitly.

**Can a judge see that the LLM is not the quantitative source of truth?** Yes — the ledger (step 12) shows 2-of-7 stages LLM, the routing reasons, and the headline claim is *computed*; the Toggle-LLM moment re-runs the pipeline deterministically with identical conclusions.

**Can a judge see what happens when the system is uncertain?** Yes — the abstention screen (step 8) refuses action and names the missing data, the owner, and the cost of waiting.

**Can a judge see how persona and decision rights change the action?** Yes — step 5 shows the same case as four briefs; step 6 shows the same SC manager authorized for ₹1.6M and blocked (escalated) at ₹3.4M.

**Can a judge see how the system handles conflicting enterprise data?** Yes — step 3: two numbers side by side, typed conflict, capped confidence, routed owner, justified working value. Never a silent merge.

**Can a judge see the system protect the business from its own decisions?** Yes — step 6 shows guardrails failing an attractive action (the promotion), second-order impacts surfacing inventory damage, and the safe alternative winning the comparison; step 6b shows two pending decisions colliding on inventory with resolution options — all before any human approval.

**Can a judge see how the system becomes better over time?** Yes — steps 7 (outcome calibrates reliability), 10–10b (feedback → governed proposal → owner merge → new contract version), 11 (memory retrieves the lesson) — and the contract version history shows the compounding.

**Can a judge see this is a general engine, not a one-off demo?** Yes — the Scenario Selector (steps 1, 13) runs a *different* business problem through the identical pipeline with no new code.

---

# FINAL THESIS

> **BI tells you what happened. ReasonFlow determines what is trustworthy enough to act on, who should act, what they should do, what must be protected, what else the decision will change, whether it conflicts with another decision, whether it worked, and what the organization learned.** The architecture makes this thesis obvious at every layer: scenario-configured KPI Contracts that own definition, drivers, thresholds, entitlements, and decision rights; a reconciliation engine that prices source disagreement into confidence before any reasoning; a deterministic quantitative core (SQL, statistics, rules, simulation) that owns every number; a certainty state machine that can refuse to act and name what would resolve the uncertainty; a Decision Record guarded by backend-evaluated guardrail KPIs, second-order impact analysis over the KPI-relation graph, collision detection across the enterprise's active decisions, and decision rights — all before a human approves; a governed contract-evolution workflow that turns learning into auditable merges, never silent mutation; institutional memory in the same Postgres store via pgvector with written similarity explanations; and an AI-governance layer — policy-gated model routing, validity-aware semantic caching, and a Transparency Ledger with real execution metadata down to ₹0.19 per insight — that proves the LLM was a labeled, routed, metered translator, never the source of truth.

---

*End of Phase 2 (v3 — FINAL). Together with `REASONFLOW_ROUND2_PRODUCT_SPEC.md`, this document is the single authoritative blueprint for Phase 3: prototype implementation. Do not code; implement this.*
