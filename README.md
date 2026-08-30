# ReasonFlow — Governed KPI-to-Decision Intelligence

BI platforms tell organizations what changed. ReasonFlow helps determine why it changed, what evidence supports that explanation, how certain the conclusion is, what actions are available, whether those actions are safe, who is authorized to approve them, and what the organization should learn from the outcome.

## At a Glance

**Problem:** The space between a KPI moving and a decision being made is unowned and ungoverned — fragmented across dashboards, conflicting data sources, and disconnected approval workflows.

**Solution:** ReasonFlow turns material KPI movements into governed investigation and decision workflows, with explicit abstention when evidence is insufficient.

**Prototype:** Illustrative seeded Apex Foods operational data, deterministic and reproducible.

**Core Workflow:** Contract → Reconcile → Detect → Investigate → Decide → Govern → Learn

**Stack:** React/Vite · FastAPI · PostgreSQL + pgvector · Redis

---

## The Problem

Enterprises run on KPIs, but the most expensive layer of the modern enterprise — the space between a KPI moving and a decision being made — is unowned.

The chain breaks at every link:

- **KPI definitions differ.** "Revenue" means invoiced net sales in ERP, recognized revenue in Finance, and sell-through in the CRM pipeline. Three teams can honestly disagree by millions because each number is valid within its own system.
- **Systems disagree structurally.** ERP updates daily at SKU-level grain; POS retail audits update weekly with a publishing lag; the Finance GL closes monthly. Any cross-source question spans different clocks, different grains, and different maps.
- **Teams act on partial truths.** Supply chain sees falling inventory and expedites; finance sees rising unit costs and withholds approval; marketing launches a promotion on a product that is out of stock. No shared evidence-backed decision context exists.
- **Statistical anomalies are not business priorities.** A small wobble in a large P&L line can matter more than a large shift in a small line. Dashboards compute statistical significance but not business materiality.
- **AI amplifies contradictory information.** A generative model given conflicting inputs does not surface the conflict — it averages it into confident prose. Fluent wrong answers are more dangerous than ugly correct dashboards, because prose buries its evidence and its uncertainty.
- **Decisions need ownership and authority.** A recommendation with no owner is an opinion. A recommendation with no authority check is a liability — either it dies in an escalation loop, or someone without authority acts on it.
- **Past decisions are forgotten.** The same "why is revenue down in the Northeast?" investigation recurs quarterly because the organization has no memory of how it resolved the question last time — what evidence mattered, what action was taken, and whether it worked.

The consequence: reconciliation consumes analyst time, contradictory cross-team actions leak margin, and decision quality is never measured.

---

## The Solution

ReasonFlow treats each KPI as a governed business object — a **KPI Contract** that carries definition, sources, drivers, thresholds, entitlements, and decision rights — and converts each material movement into a governed decision workflow.

- **Contract** — Defines what the KPI means, what sources feed it, who owns it, and who may act on it. Governance happens before any reasoning begins.
- **Reconcile** — Detects when data sources disagree and adjusts confidence based on the degree of disagreement. Conflicts are surfaced to the KPI owner, never merged silently.
- **Detect** — Evaluates whether the movement exceeds what the KPI's own history predicts, using statistical baselines and seasonal context.
- **Triage** — Calculates business materiality by combining statistical significance with financial exposure and strategic weight. Classifies movements into severity bands (CRITICAL, ELEVATED, WATCH, NOISE).
- **Investigate** — Decomposes the movement deterministically to identify root drivers. Surfaces competing hypotheses backed by traceable evidence with explicit support/contradiction states.
- **Decide** — Generates structured mitigation options locked to the contract's predefined levers. Each option is simulated on the server side with expected impact, cost, and time horizon.
- **Guard** — Checks each option against safety guardrails (e.g., minimum inventory cover, maximum cash exposure) and calculates second-order impacts on related KPIs. Detects collisions with other teams' pending decisions.
- **Govern** — Enforces decision rights: only authorized roles can approve specific actions within defined limits. Governed decisions require explicit human approval before they can be committed.
- **Learn** — Tracks the predicted outcome against the actual result. The closed case — evidence, decision, outcome, variance — is persisted into institutional memory for future reference.

---

## How Each Stage Works

### KPI Governance

Every KPI is backed by a governed contract that defines:

- **Identity:** Name, business definition (plain-language), formula (explicit and auditable), unit, business function, and owner.
- **Sources and lineage:** Which systems feed this KPI, their refresh cadence, grain, and expected tolerance bands. For example, Revenue NE is fed by ERP (daily, SKU-level), Finance GL (monthly, account-level), and POS (weekly, regional).
- **Drivers:** The known business drivers that can cause this KPI to move, ranked by prior weight. For Revenue NE, these include supplier delay, competitor promotion, marketing underperformance, and seasonality.
- **Thresholds and materiality:** Warning and critical deviation percentages, financial exposure per deviation point, margin weight, and strategic weight.
- **Decision rights:** Which roles may recommend, simulate, and approve actions, up to what financial limits, and to whom they must escalate above those limits.
- **Entitlements:** Row-level and column-level data visibility restrictions per role (e.g., Supply Chain users see only their region; unit cost columns are masked from certain roles).
- **Lifecycle:** Contract status (DRAFT → ACTIVE → CONFLICTED → UNDER_REVIEW), version history, and audit trail.

A KPI without a governed contract cannot be investigated. Incomplete contracts degrade the system loudly — for example, undefined decision rights result in explanation-only mode with no action recommendations.

### Reconciliation

Before any investigation, the system evaluates the reliability of the data feeding the KPI:

- **Source disagreement:** ERP reports one value; Finance GL reports another. The system detects this as a definition conflict (e.g., invoiced vs. recognized revenue) and lowers confidence.
- **Freshness mismatch:** POS audit data may be 6 days stale against its expected weekly cadence. Evidence from stale sources is discounted.
- **Grain mismatch:** POS at region-by-category versus ERP at SKU-by-DC. Aggregation is performed with documented information loss.
- **Coverage gaps:** Missing data windows are flagged and affected KPIs lose confidence.

The reconciliation output is a reliability score per KPI that caps downstream confidence. A conflicted picture cannot produce a full-confidence conclusion. Definition conflicts are routed to the KPI Owner for resolution.

### Detection and Materiality

KPI movements are evaluated in two dimensions:

- **Statistical significance:** Robust z-score versus seasonal baseline, outside expected confidence interval. This detects whether the movement is distinguishable from normal variation.
- **Business materiality:** Significance multiplied by financial exposure and strategic weight. This determines whether the movement deserves human attention.

Movements are classified into severity bands — CRITICAL, ELEVATED, WATCH, or NOISE. A statistically moderate deviation on a high-exposure KPI (e.g., Revenue NE at approximately ₹0.72M per deviation point) can be promoted to CRITICAL based on materiality alone.

### Investigation

The system decomposes the KPI movement deterministically:

- **Decomposition:** SQL-based breakdown of the movement into component drivers (e.g., price, volume, mix for a revenue KPI).
- **Hypotheses:** Multiple competing hypotheses are generated from the contract's known drivers and evaluated against traceable evidence.
- **Evidence:** Each evidence record carries explicit metadata: source, polarity (supporting or contradicting), freshness, lineage, method, and data classification. For the hero scenario, four pieces of evidence support "Supplier Delay" while two separate evidence records contradict "Competitor Promo" (showing the competitor promotion is concentrated in the South region, not the Northeast).
- **Confidence and abstention:** When evidence is contradictory, hypotheses tie, or data is sparse, the system enters an explicit ABSTAIN state with structured reasons. It refuses to recommend actions rather than manufacturing certainty. The cold-start scenario (Millet Noodles with only 5 weeks of history) demonstrates this: confidence is capped and the system operates in monitor-only mode.

### Decision Generation

Decision options are not invented by an LLM. They are structured levers predefined in the KPI contract:

- Each option specifies the driver it addresses, the action lever, expected impact range (low/mid/high), cost, time horizon, and the role authorized to own it.
- For Revenue NE, the seeded options include: Backup Supplier (₹1.6M cost, 42-day horizon, Supply Chain ownership), Air Freight Expedite (₹3.4M cost, 21-day horizon, escalation required), Price Promotion (₹1.1M cost, 21 days), and a Phased Promotion variant.

### Simulation and Guardrails

Each decision option is simulated on the server side:

- **Simulation:** Projects the expected change in cover days, on-shelf availability recovery, margin impact, and direct effects on related KPIs.
- **Guardrails:** Hard safety thresholds that automatically block execution. For the hero scenario, these include: gross margin floor (-1%), inventory cover minimum (5 days), cash exposure maximum (₹2M), and customer SLA minimum (95% on-shelf availability).
- **Guardrail results:** Each option receives a status — PASS, WARNING, FAIL, or NOT_SAFE. Hard guardrail violations block approval at the backend.

### Second-Order Impacts and Collisions

KPIs are connected through defined relationships with typed edges (IMPACTS, PRECEDES) carrying elasticity, confidence, and lag:

- A price promotion that boosts revenue can simultaneously drain inventory cover below the safe minimum. The system calculates this propagation.
- A pending procurement decision to reduce safety stock on the same lane can collide with a supply-switch decision. The system detects such collisions.

### Decision Rights

Decision authority is strictly governed:

- **Supply Chain** may approve supply-switch and expedite actions up to ₹2M. Actions above ₹2M require executive escalation.
- **Executive** may approve actions up to ₹10M, including overriding standard constraints with an auditable justification.
- **Analyst** may recommend and simulate but has no approval rights.
- **Marketing** may recommend promotions but approval is routed to Executive.

The backend enforces these limits. A Supply Chain manager attempting to approve a ₹3.4M air freight expedite receives a denial with escalation routing to the Executive role.

### Outcome and Feedback

After a decision is committed and the monitoring period elapses:

- The system records the predicted versus actual outcome and the variance.
- Feedback can influence future reasoning, but contract changes (e.g., adjusting driver weights or thresholds) require governed review.

### Institutional Memory

Every closed investigation — its evidence, actions, outcomes, and lessons — is persisted as a retrievable case. When a new anomaly occurs, the system performs an entitlement-aware similarity search to surface relevant past cases.

The hero scenario includes a seeded historical case: "NE Q3 2025 — Supplier delay at Guwahati DC" where backup supplier activation recovered ₹3.1M within the expected band. This case is surfaced when the current hero investigation runs, providing precedent context.

For the cold-start Millet Noodles scenario, three launch-analogue cases (Atta Premium, Oils Blend, Snacks Range Extension) serve as sibling references when direct history is insufficient.

Memory is stored using PostgreSQL with pgvector (256-dimensional embeddings, deterministic feature-hash method). Retrieval respects organizational and role-based entitlements.

### Transparency and AI Governance

The system tracks every stage of the pipeline:

- **Method labeling:** Each stage records whether it used deterministic logic (SQL, statistics, business rules) or governed AI capabilities (hypothesis drafting, evidence-text extraction, narrative translation).
- **Routing:** A capability-based routing gateway directs tasks to the appropriate method. Governed AI is used only for labeled, metered tasks.
- **Fallback:** If the LLM is unavailable, the pipeline operates in deterministic mode. Business conclusions, numerical outputs, and decision options remain intact.
- **Telemetry:** Execution latency, model/route used, cache behavior, and cost information are recorded per stage.

---

## KPIs in the Prototype

The prototype demonstrates seven governed KPIs for the fictitious FMCG company Apex Foods:

### Business KPIs

| KPI | What it measures | Unit | Region |
|---|---|---|---|
| Revenue — Northeast | Invoiced net sales for the NE region, all channels | INR (millions) | NE |
| On-Shelf Availability — NE | Share of audited SKU-store combinations found on shelf | Percentage | NE |
| Inventory Days-of-Cover — NE | Forward days of demand covered by on-hand stock at NE DCs | Days | NE |
| Marketing ROI | Incremental revenue per rupee of campaign spend | Ratio | National |
| Supplier Reliability — NE Lane | On-time-in-full delivery rate for NE-lane suppliers | Percentage | NE |
| Sales per Outlet — South | Average weekly sales per outlet (abstention demo case) | INR (thousands) | South |
| Millet Noodles Revenue — Launch | Revenue for the newly launched Millet Noodles line (cold-start demo) | INR (millions) | National |

These KPIs are interconnected: Supplier Reliability impacts Inventory Cover, which impacts On-Shelf Availability, which impacts Revenue. This chain enables second-order impact calculation.

### Investigation Metrics

- **Materiality:** Combines statistical significance with financial exposure and strategic weight to determine severity (CRITICAL / ELEVATED / WATCH / NOISE).
- **Confidence:** Derived from reconciliation reliability, evidence quality, data freshness, and hypothesis support strength. Capped by upstream conditions — conflicted sources reduce downstream confidence.
- **Abstention reasons:** Structured fields explaining why the system declined to recommend (e.g., tied hypotheses, sparse history, stale evidence, unresolved conflict).

### Decision Metrics

- **Expected impact:** Projected financial recovery in INR, expressed as a range (low / mid / high).
- **Cost:** Direct cost of executing the action.
- **Horizon:** Time in days for the action to take effect.
- **Guardrail status:** PASS, WARNING, FAIL, or NOT_SAFE based on hard and soft threshold checks.
- **Second-order impact:** Projected effect on related KPIs (e.g., cover-days change, OSA recovery percentage, margin delta).
- **Collision state:** Whether this decision conflicts with another pending decision on the same or related KPIs.

### System Metrics

- **AI telemetry:** Execution stage, method used (deterministic vs. LLM), latency, model/route, cache behavior, and cost/token information where applicable.

---

## Personas

ReasonFlow serves four personas viewing the same underlying analytical truth, with narrative depth and available actions tailored to their role:

### Executive (CEO / CFO / COO)

- **Needs:** Financial exposure, cost of waiting, and the strategic decision required.
- **Sees:** High-level materiality, top drivers, aggregated impacts. Unit cost columns are masked.
- **Can do:** Approve escalated strategic decisions up to ₹10M. Override standard constraints with an auditable justification.

### KPI Owner / Data Steward

- **Needs:** Contract accuracy, data source health, definition integrity.
- **Sees:** Full lineage, source ledgers, contract proposals, and governance data across all regions and domains.
- **Can do:** Resolve data conflicts that block downstream analysis. Update KPI thresholds and merge contract evolution proposals.

### Supply Chain (Operations)

- **Needs:** Operational drivers, specific mitigation levers, execution risk.
- **Sees:** Row-level operational data for their region (NE). Unit cost and marketing ROI columns are masked.
- **Can do:** Simulate options and approve actions within their ₹2M authorized limit. Actions exceeding this limit are escalated to the Executive role.

### Analyst

- **Needs:** Methodologies, decomposition math, evidence reliability, and AI telemetry.
- **Sees:** Full visibility into formulas, evidence states, contradiction details, and system metrics across all regions.
- **Can do:** Challenge hypotheses, correct drivers, submit feedback. Has no execution approval rights — can recommend and simulate but cannot commit a business action.

---

## Hero Scenario

**Revenue Decline — Northeast (Apex Foods, Instant Noodles)**

This scenario demonstrates the complete ReasonFlow workflow using illustrative seeded data:

1. **KPI movement.** The system detects that Northeast Revenue has declined 12% versus the seasonal baseline. The financial exposure (approximately ₹8.6M at this deviation) promotes the anomaly to CRITICAL.
2. **Source conflict.** ERP reports ₹84M; Finance GL reports ₹87M for the same region and period. The reconciliation layer flags a definition conflict — the gap is explained by the difference between invoiced revenue (ERP, daily) and recognized revenue (GL, monthly close with returns accrual). POS data is also flagged as stale (6-day publishing lag). Overall confidence is lowered.
3. **Investigation.** Deterministic decomposition identifies the root drivers — volume decline is the primary contributor.
4. **Competing hypotheses.** Four hypotheses are evaluated against traceable evidence:
   - "Supplier Delay" — supported by four pieces of evidence (supplier delay notice, OTIF drop from 94 to 81, days-of-cover collapse from 11.6 to 5.1, and OSA decline from 90.8 to 71.4).
   - "Competitor Promo" — contradicted by two pieces of evidence (the competitor promotion is concentrated in the South region; NE promo-price index is flat).
   - "Marketing Underperformance" — weakly supported by a stale mix report but contradicted by a fresh campaign report showing spend within plan.
   - "Seasonality" — minimal prior weight with no strong supporting evidence.
5. **Decision options.** The system surfaces structured mitigation options mapped to the KPI contract:
   - Option A (Activate Backup Supplier): ₹1.6M cost, 42-day horizon, expected recovery ₹2.9M–₹5.2M.
   - Option B (Air Freight Expedite): ₹3.4M cost, 21-day horizon, expected recovery ₹3.4M–₹5.8M.
   - Option C (Price Promotion +10% in NE): ₹1.1M cost, 21-day horizon.
6. **Guardrails and second-order impacts.** Option A passes all guardrails (cash exposure ₹1.6M is below the ₹2M threshold). Option B exceeds the cash-exposure guardrail (₹3.8M total exposure) and is blocked. Option C triggers a second-order impact: the revenue boost drains inventory cover below the 5-day hard minimum and is marked NOT SAFE.
7. **Decision rights.** The Supply Chain manager is authorized to approve Option A (₹1.6M is within their ₹2M limit). Option B would require executive escalation.
8. **Institutional memory.** The system surfaces a relevant historical case: "NE Q3 2025 — Supplier delay at Guwahati DC" where backup supplier activation recovered ₹3.1M within the expected band.
9. **Outcome.** The approved decision, its evidence, and its projected outcome are saved for future reference.

All values in this scenario are from the illustrative seeded prototype data.

---

## What the Prototype Demonstrates

- KPI governance (contracts enforced before reasoning)
- Multi-source reconciliation and conflict detection
- Materiality-based detection and triage
- Deterministic investigation and decomposition
- Competing hypotheses with traceable evidence
- Uncertainty evaluation and explicit abstention
- Cold-start handling (Millet Noodles with 5 weeks of history)
- Structured decision options locked to contract levers
- Server-side simulation
- Safety guardrails and second-order impact analysis
- Decision collision detection
- Role-based decision rights enforcement
- Human approval workflow
- Outcome tracking and feedback
- Institutional memory with entitlement-aware retrieval
- AI transparency and governance telemetry
- Three operating scenarios on a shared reasoning engine

---

## Product Workflow

```text
Operational Signal
       ↓
KPI Governance (Contract)
       ↓
Source Reconciliation
       ↓
Detection & Materiality
       ↓
Investigation & Evidence
       ↓
Deterministic Reasoning
       ↓
Decision Options
       ↓
Simulation & Guardrails
       ↓
Decision Rights & Human Approval
       ↓
Outcome & Learning
```

---

## Data Strategy

The prototype uses deterministic seeded data for a fictitious FMCG company, Apex Foods.

**Why illustrative data?** Deterministic seed data guarantees reproducibility: the same scenario produces the same analytical conclusions, the same evidence rankings, and the same guardrail outcomes on every run. This provides a controlled demonstration environment where evaluators can trace the complete workflow from signal to decision without external dependencies.

The seed includes seven governed KPIs, five data sources (ERP, Finance GL, POS, WMS, Supplier Scorecard), four personas with configured rights and entitlements, three operating scenarios, and four historical memory cases.

This is not real customer or enterprise data.

---

## Why Deterministic Reasoning with Governed AI

The LLM is not the source of quantitative truth in ReasonFlow.

**Quantitative reasoning** — detection, decomposition, materiality, simulation, guardrail checks, second-order propagation — is handled by deterministic analytical logic: SQL, statistics, and business rules. These outputs are reproducible and verifiable.

**Governed AI capabilities** are used strictly for labeled, metered tasks:
- Hypothesis drafting
- Evidence-text extraction
- Persona-specific narrative translation

Each AI usage is labeled with its method, metered for cost and latency, and recorded in the transparency ledger. If the LLM is disabled or unavailable, the pipeline operates in deterministic mode — business conclusions, numerical outputs, and decision options remain intact.

**Why this matters:** Deterministic quantitative reasoning prevents hallucinated numbers from entering the decision workflow. Governed routing prevents uncontrolled AI costs. Fallback behavior ensures the system remains operational without an LLM dependency.

---

## Architecture

- **React / Vite** — Interactive, persona-aware decision workspace.
- **FastAPI** — Deterministic reasoning pipeline, capability routing, authorization enforcement, and decision-rights gating.
- **PostgreSQL 16 + pgvector** — Canonical system of record for structured data, KPI contracts, decision records, and institutional memory (256-dimensional vector embeddings for case similarity retrieval).
- **Redis 7** — Semantic caching and rate-limiting to control AI costs and latency.

## Technology Stack

- **Frontend:** React, TypeScript, Vite, Tailwind CSS, Vitest
- **Backend:** Python, FastAPI, SQLAlchemy 2, Pydantic, Alembic, psycopg 3
- **Data / Infrastructure:** PostgreSQL 16, pgvector, Redis 7, Docker Compose
- **AI / Reasoning:** Deterministic reasoning baseline, configurable LLM routing, fallback/degraded behavior, AI usage telemetry

---

## Business Value

ReasonFlow creates value through concrete operational mechanisms:

- **Faster investigation** — Automated detection, decomposition, and evidence assembly reduce the time from anomaly to structured diagnosis.
- **Reduced manual reconciliation** — Source conflicts are surfaced and classified before analysis, replacing ad-hoc cross-team reconciliation.
- **Safer action selection** — Server-side simulation, guardrails, and second-order impact analysis surface risks before commitment.
- **Clearer accountability** — Enforced decision rights ensure actions are approved by authorized roles within defined limits.
- **Reusable organizational knowledge** — Institutional memory accumulates from every closed case, providing precedent context for future investigations.
- **Controlled AI usage** — Governed routing, semantic caching, and deterministic fallback control LLM costs and prevent hallucinated outputs from reaching business conclusions.
- **Auditable decisions** — The transparency ledger provides a traceable record of every stage, method, and cost.

The prototype demonstrates these mechanisms. Production impact would depend on enterprise deployment with real operational data.

---

## Roadmap

| Phase | Status |
|---|---|
| Working prototype with illustrative seeded data | Current |
| Pilot with real enterprise operational data | Future |
| Enterprise integration (SSO, live ERP/POS connectors) | Future |
| Scaled continuous learning and cross-tenant memory | Future |

---

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Data conflicts and source disagreement | Explicit multi-source reconciliation with confidence penalties |
| Uncertainty and overconfidence | Confidence evaluation and explicit abstention triggers |
| Unsafe or infeasible actions | Server-side simulation, safety guardrails, and second-order impact analysis |
| Unauthorized action execution | Backend-enforced decision rights and role-based approval limits |
| AI failure or unavailability | Deterministic quantitative reasoning layer with graceful fallback |
| AI cost and latency growth | Governed routing, semantic caching, and metered LLM usage |

---

## Running Locally

**Prerequisites:** Docker Desktop and Git.

```bash
docker compose up -d --build
```

```bash
docker compose ps
```

- **Frontend:** http://localhost:5173
- **API Documentation:** http://localhost:8000/docs

---

## Demo Personas

Prototype demo credentials only — not production credentials.

**Password:** `ReasonFlow#2026`

| Persona | Email |
|---|---|
| Analyst | `meera.analyst@apexfoods.example` |
| Executive | `priya.ceo@apexfoods.example` |
| KPI Owner | `vikram.owner@apexfoods.example` |
| Supply Chain | `rahul.sc@apexfoods.example` |

---

## Validation

The prototype is backed by automated frontend and backend validation.

Detailed acceptance evidence is documented in:
`docs/FINAL_ACCEPTANCE_QA.md`
