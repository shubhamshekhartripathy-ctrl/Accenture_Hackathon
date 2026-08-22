# REASONFLOW ROUND 2 — PRODUCT SPECIFICATION

**Product:** ReasonFlow — Governed KPI-to-Decision Platform
**Phase:** 1 of 3 (Product Strategy → Product Specification → Architecture & Prototype)
**Track:** Accenture Innovation Challenge 2026, Round 2 — Problem Track 3: BusinessIntelligence.ai
**Status:** CONCEPT LOCKED — this document is the authoritative product definition for the architecture phase. The next phase must implement this spec, not reinterpret it.

---

# 1. EXECUTIVE PRODUCT THESIS

**ReasonFlow is the governed layer between enterprise BI and business action.** It turns each important KPI into a *living business object* — a KPI Contract that carries definition, sources, drivers, thresholds, entitlements and decision rights — and converts each material KPI movement into a reconciled, evidence-backed, persona-aware, human-approved, outcome-tracked **Decision Record**.

**The category claim:** BI platforms end at insight (dashboards stop at the number). ERP/workflow systems begin at execution (they act on instructions). **Nobody owns the middle** — KPI meaning, source reconciliation, materiality, interpretation, uncertainty, evidence, persona context, decision rights, action, monitoring, outcomes, organizational memory. ReasonFlow owns the governed middle.

**The trust doctrine (non-negotiable):** the LLM never computes a number. Every quantitative output is produced by deterministic logic, SQL, business rules, statistics, or ML, and every stage is labeled with its method. The LLM's three legitimate jobs are: hypothesis drafting, evidence-text extraction, and persona narrative translation — all labeled, metered, and optional (the pipeline runs in deterministic mode without it).

**The compounding asset:** every decided case — evidence, decision, outcome, calibration — accumulates into decision memory, so each similar future case is recognized, explained, and decided faster, cheaper, and with better-calibrated confidence. Defensibility compounds with every recorded decision.

**One-line positioning:** *"Where KPI movements become governed decisions."*

---

# 2. FINAL PROBLEM STATEMENT

Enterprises run on KPIs, but the most expensive layer of the modern enterprise — the space between a KPI moving and a decision being made — is unowned and ungoverned.

**Why the chain breaks.** In the ideal chain `DATA → KPI → INTERPRETATION → DECISION → OUTCOME`, each link silently drifts:

- **KPI definitions differ.** "Revenue" means invoiced net sales in ERP, recognized revenue under accounting rules in the finance close, and sell-through in the CRM pipeline. Three teams briefing the same executive can honestly disagree by millions — every number is "valid," none is *the* number. The definition lives in people's heads and spreadsheets, not in a governed object.
- **Systems disagree structurally.** ERP updates daily at SKU×DC grain; the POS retail audit updates weekly at region×category grain with a six-day publishing lag; the finance GL closes monthly. Any cross-source question is therefore a question about *three different clocks and three different maps* — and nobody reconciles them before reasoning.
- **Teams disagree even with valid data.** Supply chain sees falling inventory and expedites; finance sees rising unit costs and withholds approval; marketing sees a volume dip and launches a promotion — on a product that is out of stock. Each team acts on its own partial truth because no shared, evidence-backed decision context exists.
- **Statistical anomalies are not business priorities.** A 0.4σ wobble in a ₹900M P&L line can matter more than a 5σ shift in a ₹20K line. Statistical significance answers "is this noise?" — it cannot answer "is this worth executive attention?" Only business materiality can, and dashboards don't compute it.
- **AI amplifies contradictory enterprise information.** A fluent generative model given conflicting inputs does not surface the conflict — it averages it into smooth, confident prose. Fluent wrong answers are more dangerous than ugly correct dashboards, because prose buries its evidence and its uncertainty.
- **A confident answer without evidence is dangerous.** When the model says "supplier disruption caused the decline" and is wrong, the enterprise burns cash on expedited freight for a problem it doesn't have. Confidence without traceability is not analysis; it is risk.
- **Different decision-makers need different outputs.** The CEO needs exposure and a decision; the analyst needs method and evidence; the operations lead needs a lever, an owner, and a monitoring plan. One generic narrative serves none of them well.
- **Decisions need ownership and rights.** A recommendation with no owner is an opinion. A recommendation with no authority check is a liability — either it dies in an escalation loop, or someone without authority acts on it.
- **Past decisions are forgotten.** The same "why is revenue down in the Northeast" argument recurs every quarter because the company has no memory of how it resolved the question last time — what evidence mattered, what action was taken, and whether it worked.

**The consequence:** reconciliation and alignment consume days of analyst and executive time; contradictory cross-team actions leak margin; decision quality is never measured; and every quarter the enterprise re-litigates what it already learned.

**The structural gap:** BI owns `DATA → KPI`. ERP owns `DECISION → OUTCOME`. **Nobody owns `KPI → INTERPRETATION → DECISION`.** That unowned middle is where trust is built or destroyed, and it is exactly what ReasonFlow owns.

---

# 3. PRODUCT CATEGORY & POSITIONING

| Element | Definition |
|---|---|
| **Name** | ReasonFlow |
| **Category** | Governed KPI-to-Decision Platform |
| **Positioning** | "Where KPI movements become governed decisions." |
| **For** | Enterprises whose important KPIs span heterogeneous systems and whose decisions currently live in meetings, spreadsheets, and memory |
| **Unlike** | BI dashboards (stop at insight), chatbots over SQL (no governance, no evidence, no rights), semantic layers (definitions only, no decisions or outcomes), data-quality tools (fix data, ignore decisions) |
| **Because** | ReasonFlow is the only layer that governs the full arc from KPI meaning to outcome-tracked decision — with a deterministic quantitative core and an LLM used strictly as a labeled translator |
| **Commercial posture** | Sits **alongside** the enterprise BI/ERP stack, never asks for migration, and accumulates value: every decided case compounds memory and calibration |

**The one-sentence category defense, used everywhere:** *"BI ends at insight. ERP begins at execution. ReasonFlow owns the governed middle."*

---

# 4. CORE INSIGHT

**A KPI is not merely a number. It is a governed business object.**

A KPI carries: definition, formula, owner, sources, lineage, refresh cadence, drivers, thresholds, materiality rules, entitlements, decision rights, current state, open investigations, decisions, outcomes, and historical context. Traditional BI strips a KPI down to its latest value and discards everything else — which is precisely why interpretation drifts.

ReasonFlow treats the KPI as the primary, persistent, governed object and organizes all intelligence around its **decision lifecycle**:

```
DEFINED → FED → MEASURED → RECONCILED → MOVED → INVESTIGATED → DECIDED → MONITORED → LEARNED
   ↑                                                                                    │
   └────────────────── every pass enriches the contract ────────────────────────────────┘
```

An investigation is not the product's spine (as in Round 1); it is a *lifecycle state* of a KPI. The product's spine is the KPI Contract, and its signature output is the Decision Record.

---

# 5. PRODUCT OBJECTS

Five objects define the product. Everything else in the specification hangs off them.

### 5.1 Primary object — KPI Contract
The governed definition of what a KPI means and how it may be used. It is the anchor for reconciliation, detection, materiality, entitlements, decision rights, and learning. **What the user actually interacts with:** a KPI Case File — a persistent page per KPI that shows its contract, its current reconciliation state, its open movement, its investigation, and its decision history. The KPI Case File is the product's home screen in spirit; everything else is a tab or a queue built from contracts.

### 5.2 Operational object — Decision Record
The outcome of the DECIDE stage, following the official PS schema: **driver → controllable lever → action → expected impact → owner → confidence → monitoring plan**, extended with constraints checked, decision-rights verdict, evidence used, simulation version, human decision, actual outcome, outcome variance, and updated reliability. A Decision Record is versioned, rights-checked, human-approved, and outcome-tracked. It is the unit of enterprise accountability — and the unit of compounding memory.

### 5.3 Analytical object — KPI Movement / Investigation
A material movement detected on a KPI (e.g., "Revenue NE −12% vs seasonal baseline") becomes a bounded investigation: decomposition, competing hypotheses, evidence, certainty state. Investigations are created from contracts, inherit the contract's drivers and entitlements, and end in either a Decision Record, a clarification request, or an abstention.

### 5.4 Evidence object — Evidence Record
Every claim is backed by Evidence Records, and every Evidence Record points to a source document/row with timestamp, freshness, lineage, and analytical method. Evidence carries one of four states — **supporting, contradicting, stale, restricted** — and no narrative claim may exist without it.

### 5.5 Organizational memory object — Decision / Case History
Closed investigations (with or without decisions) become retrievable cases linked to their KPIs, entities, drivers, and outcomes. Memory powers: (a) "this looks like the NE Q3 case" retrieval, (b) sparse-history analogue borrowing, (c) pattern reliability calibration. Memory is per-tenant, entitlements-scoped, and carries written similarity explanations.

**Object relationships (one sentence each):** A Contract *governs* a KPI. A Movement *occurs on* a KPI and *inherits* its contract. Evidence Records *support or contradict* hypotheses *inside* a movement. A Decision Record *resolves* a movement and *belongs to* a KPI. Case History *accumulates* from closed movements and *enriches* future contracts.

---

# 6. CORE PRODUCT LOOP

```
CONTRACT → RECONCILE → DETECT → TRIAGE → EXPLAIN → DECIDE → LEARN
   ↑                                                           │
   └───────────── (every pass enriches the contract) ──────────┘
```

| Stage | Question it answers | Quantitative truth produced by | LLM role (if any) |
|---|---|---|---|
| **CONTRACT** | What does this KPI *mean*, and who may act on it? | Declarative rules + lineage metadata | None |
| **RECONCILE** | How reliable is our current *picture* of this KPI? | Cross-source comparison rules, freshness scoring | None |
| **DETECT** | Did it move beyond what its own history predicts? | Seasonal baselines, robust statistics, CIs | None |
| **TRIAGE** | Is the movement *material* enough for human attention? | Materiality rules (significance × business impact) | None |
| **EXPLAIN** | What drove the movement, and how sure are we? | SQL contribution decomposition, retrieval scoring, graph checks, calibration | Hypothesis drafting, evidence-text extraction, narrative translation (labeled) |
| **DECIDE** | Who should do what, within what authority, with what expected result? | Server-side simulation, rights checks, constraint checks | Option phrasing (labeled) |
| **LEARN** | Did it work — and what should we believe next time? | Outcome comparison, shrinkage-calibrated reliability, feedback rules | Case summarization into memory (labeled) |

Two loop invariants, enforced by design:
1. **Every stage writes a durable, versioned artifact** — a stage never passes only prose downstream.
2. **Every number has a labeled deterministic method; every LLM use is labeled and metered.**

---

# 7. KPI CONTRACT

### 7.1 Fields (conceptual)

| Field group | Contents |
|---|---|
| Identity | KPI name, business definition (plain-language, one paragraph), formula (explicit, auditable), unit, business function, owner (named role + person) |
| Source & lineage | Source systems, per-source lineage (which table/feed/transform), refresh cadence per source, data grain per source, hierarchy/canonical entity mapping, calendar & business rules (fiscal calendar, returns accrual, adjustments) |
| Behavior | Known drivers (ranked, editable), expected range (seasonal), warning threshold, critical threshold, materiality rules (₹ exposure per point, margin weight, strategic weight) |
| Governance | Data-quality rules (tolerance bands, null rules, duplicate rules), entitlement rules (row/column/domain scopes per role), decision rights (who may approve which actions up to which limits), related KPIs |
| Lifecycle | Contract status (DRAFT → ACTIVE → CONFLICTED → UNDER_REVIEW), version history, open investigations, historical decisions, outcome history |

### 7.2 Why the contract exists
- It **prevents interpretation drift**: one governed definition replaces five team-specific ones.
- It **makes reconciliation meaningful**: conflicts are detected *against the contract*, not ad hoc.
- It **constrains the reasoning space**: hypotheses must connect to contract drivers; actions must pass contract decision rights.
- It **enforces entitlements at the object level**: who may see and act on this KPI is part of the KPI, not a bolt-on.
- It **makes learning cumulative**: corrections, outcomes, and new drivers land *in the contract*, so the next case starts smarter.

### 7.3 What happens if the contract is inconsistent or incomplete (designed degradation)
| Contract gap | System behavior |
|---|---|
| No thresholds | DETECT still runs statistically, but TRIAGE marks materiality "statistical-only, low confidence" — never promotes to CRITICAL |
| No known drivers | Hypothesis space shrinks to decomposition-derived drivers only; EXPLAIN confidence capped |
| No decision rights | No action recommendations at all — explanations only, with an explicit banner "decision rights undefined; KPI owner action required" |
| No owner | Conflicts and clarification requests cannot be routed → case enters ABSTAIN with "owner unassigned" as the blocking reason |
| Contradictory formula (two sources define it differently) | Contract status → CONFLICTED; reconciliation raises a definition conflict; certainty state capped at CLARIFY |

The message to users and judges: **incomplete governance degrades the product loudly and honestly — it never fabricates it.**

---

# 8. RECONCILIATION INTELLIGENCE

Reconciliation is *not* ETL and not data cleaning. It is the intelligence layer that reasons about the **reliability of the inputs before reasoning about the business event**.

### 8.1 What ReasonFlow evaluates
| Concern | Example in demo data | Reconciliation verdict |
|---|---|---|
| **Source disagreement** | ERP says Revenue = ₹84M; Finance GL says ₹87M for the same region/period | Definition conflict detected (invoiced vs recognized; returns accrual; calendar) |
| **Definition mismatch** | Two feeds compute the same KPI differently | CONFLICTED → routed to KPI owner, working value retained with justification, never silently merged |
| **Freshness mismatch** | POS audit is 6 days stale vs its weekly cadence; WMS is current | Evidence from stale source is discounted; confidence capped |
| **Grain mismatch** | POS at region×category vs ERP at SKU×DC | Aggregation performed with documented information loss; comparison flagged "coarse-grain" |
| **Hierarchy mismatch** | "NE-04" / "Northeast Territory" / "Region X" | Canonical entity resolution before any comparison |
| **Calendar mismatch** | Finance close covers a different period boundary than ERP daily sums | Period normalization with explicit alignment rule |
| **Missing data** | WMS has no stock movements for 3 days | Coverage gap flagged; affected KPIs lose confidence |
| **Entity mismatch** | POS SKU "MilletNoodles_120g" vs ERP material "MN-120" | Alias resolution; unresolvable → flagged |

### 8.2 The conceptual flow
For each KPI, the reconciler maintains a **source ledger**: every feed claiming to contribute, with system, cadence, grain, last refresh, coverage window, and current values at comparison points. On each refresh cycle (and always before any investigation):
1. **Normalize** — canonical entities, calendar alignment, unit/currency.
2. **Compare** — same-meaning values across sources vs tolerance bands from the contract's data-quality rules.
3. **Classify** — each discrepancy is typed (definition / refresh / grain / hierarchy / calendar / coverage) and given a severity.
4. **Score** — a *reliability of the current picture* score per KPI, which **caps** downstream confidence (a conflicted picture cannot yield an ACT-state conclusion).
5. **Route** — definition conflicts → KPI owner; refresh/coverage issues → data owner; grain issues → analyst note.

### 8.3 What the user sees (Reconciliation tab of the KPI Case File)
- A verdict banner: `CONSISTENT · MINOR · CONFLICTED` with the reliability score.
- A conflict card per issue: the two numbers side by side, the detected mismatch type, the confidence impact, the suggested resolution, and the routed owner.
- A freshness profile: last refresh per source vs expected cadence, with stale sources visibly discounted.
- The **working value** and its justification: "Working value ₹84.0M (ERP, invoiced, daily) — Finance recognized ₹87.0M deferred to monthly close reconciliation. Confidence impact: −0.12."

**The product rule:** ReasonFlow never merges conflicting numbers silently, and never reasons on a conflicted picture at full confidence.

---

# 9. MATERIALITY INTELLIGENCE

Anomaly detection and materiality are different questions. Statistical significance asks *"is this noise?"* Materiality asks *"is this worth executive and analyst attention?"* ReasonFlow computes both, separately, and combines them.

### 9.1 Statistical significance
Robust z-score vs seasonal baseline, outside expected CI, anomaly score, with the method and model version persisted per detection. Detects *movement*.

### 9.2 Business materiality
| Factor | Contribution |
|---|---|
| Magnitude | % deviation and absolute ₹ deviation vs expected range |
| Revenue exposure | ₹ at risk per point of deviation (from contract) |
| Margin impact | where the movement hits margin, not just topline |
| Strategic importance | strategic weight in the contract (a launch KPI outranks a legacy line) |
| Risk | downside asymmetry (inventory risk vs cosmetic metric) |
| Business thresholds | warning/critical bands from the contract |

### 9.3 The materiality score (conceptual)
```
Materiality = Significance (0–1) × Business Impact (weighted ₹/margin/strategic exposure)
Priority bands:  CRITICAL · ELEVATED · WATCH · NOISE
```
- A statistically strong move on a small line lands in WATCH — saved from executive attention.
- A modest statistical move on a huge P&L line is *promoted* to ELEVATED/CRITICAL by business impact alone.
- The score and its factors are always visible: "−12% (5.1σ) × ₹8.6M exposure × strategic weight 0.8 → CRITICAL."

The result answers the PS's implicit question: **"Is this KPI movement important enough to consume executive/analyst attention?"** — with the arithmetic shown.

---

# 10. EXPLAIN / REASONING ENGINE

This stage preserves and extends the strongest Round 1 machinery: deterministic analytics, contribution analysis, competing hypotheses, supporting/contradicting evidence, source-linked evidence, confidence, reasoning paths, uncertainty. Its design rule: **quantitative truth and generative intelligence are explicitly separated.**

### 10.1 The two-layer split

| | **Quantitative truth layer** | **Generative layer** |
|---|---|---|
| Methods | SQL, deterministic logic, statistics, ML, contribution analysis, retrieval scoring, graph checks, calibration | LLM: hypothesis drafting, evidence-text extraction, narrative translation |
| Constraint | Owns every number in the product | Owns zero numbers |
| Failure mode | Deterministic; reproducible; versioned | Optional; labeled; replaceable; pipeline runs without it |

### 10.2 Conceptual flow (numbered, auditable)
1. **DETECT** — seasonal baseline, forecast blend, robust z, CI, anomaly score. *Method: statistics. LLM: no.*
2. **DECOMPOSE** — deterministic contribution analysis: price / volume / mix; region / SKU / channel; calendar-normalized. *Method: SQL + business rules. LLM: no.* This is the quantitative spine of the explanation.
3. **HYPOTHESIZE** — candidate drivers seeded from the contract's known drivers and the graph neighborhood, then drafted into competing hypotheses. *Method: config templates + LLM drafting (labeled).*
4. **GATHER** — scoped retrieval (time window, region, product, entity) across structured rows and documents; claims extracted. *Method: retrieval + extraction (extraction labeled if LLM).*
5. **SCORE** — each hypothesis scored on supporting vs contradicting evidence: keyword/semantic hits raise support; contradiction phrases ("spend within plan", "NPS held") raise contradiction; graph path existence checked; temporal alignment checked. *Method: rules + ML. LLM: no.*
6. **RANK & CALIBRATE** — hypotheses ranked; confidence composed from evidence balance, freshness, source agreement, historical pattern reliability, hypothesis separation; shrunk when history is thin. *Method: rules + statistics. LLM: no.*
7. **CERTAINTY STATE** — ACT / ACT WITH CAUTION / CLARIFY / ABSTAIN assigned by rules. *LLM: no.* (Section 11.)
8. **NARRATE** — only now, the structured conclusion object is translated into persona-specific narrative; numbers are injected from the conclusion object, never generated. *Method: LLM (labeled, optional).*

**Invariant:** the LLM can reword a conclusion; it can never change its numbers, ranks, or certainty state. Narrative is rendered *from* the structured object — if the narrative text disagrees with the object, the object wins (rendering is deterministic from fields).

### 10.3 What the user sees
The Investigation tab: decomposition waterfall (each component a clickable SQL-backed figure); the ranked hypothesis list with **supporting and contradicting evidence side by side**; a reasoning path (graph traversal, e.g., `Apex Supplier → DELAYED_BY → Guwahati DC → IMPACTS → OSA → IMPACTS → Revenue`); the confidence composition; and the certainty state banner. Language discipline: "likely driver", "evidence suggests", "confidence" — never "cause proven."

---

# 11. ABSTENTION & UNCERTAINTY

Uncertainty is not a percentage appended to an answer. It is a **certainty state machine** that governs what the product is allowed to do next.

### 11.1 The state machine

| State | Entered when | Downstream behavior |
|---|---|---|
| **ACT** | Confidence ≥ act threshold; top driver lead ≥ 0.15; no contradiction; sources fresh; rights defined | Full decision workspace: options, simulation, approval |
| **ACT WITH CAUTION** | Confidence 0.50–0.70, or one moderate risk factor (e.g., slightly stale source) | Options carry wider impact ranges; monitoring plan mandatory; approval required regardless of amount |
| **CLARIFY** | A specific, cheaply resolvable gap exists with a named owner (e.g., POS feed not refreshed; sample composition unconfirmed) | A clarification request is issued; the case parks; it automatically resumes when the named data arrives |
| **ABSTAIN** | Confidence < 0.50; or top hypotheses statistically tied; or contradictory evidence; or contract conflict; or history insufficient and no analogue | **No action options are offered.** The product states "do not act yet" and explains what would resolve it |

### 11.2 Abstention triggers (each mapped to a demo-able cause)
Contradictory evidence · stale source · insufficient history · KPI definition conflict · insufficient supporting evidence · permission-limited evidence (entitlements hide part of the picture — flagged, never silently compensated).

### 11.3 What the abstention screen always contains
1. **Why it cannot safely conclude** — the trigger, in plain language.
2. **What evidence conflicts** — the two sides, with openable sources.
3. **What information is missing** — the named gap.
4. **What data would resolve the uncertainty** — the specific feed, field, or confirmation.
5. **Who should provide it** — routed owner (from the contract).
6. **Whether action should wait** — cost-of-waiting vs cost-of-acting: "Expected cost of waiting: low. Expected cost of acting on the wrong driver: ~₹2.4M. Recommendation: wait."

**Why this is a differentiator, not a defect:** an executive trusts a system that says "do not act yet, here is why, here is what would settle it" far more than one that confidently narrates noise. This is the product's honesty made visible.

---

# 12. SPARSE-HISTORY / COLD-START MODE

For newly launched products, new markets, or new KPIs, the product must behave *differently*, not merely less confidently. Cold start is a **mode**; abstention is a **state** — a cold-start KPI can still CLARIFY, but it almost never reaches ACT.

### 12.1 Entry conditions
Observation count below minimum (e.g., < 13 periods or < 2 full business cycles), or launch flag set in the contract.

### 12.2 Cold-start behaviors
| Behavior | What it does |
|---|---|
| **Peer/sibling analogue borrowing** | Transfers the seasonal shape of sibling KPIs (same category, similar market) with an explicit discount factor; analogues are named and clickable |
| **Benchmark-based reasoning** | Category/market benchmark bands stand in for history |
| **Early-life control limits** | Wider control bands reflecting launch volatility |
| **Wider uncertainty intervals** | CIs expanded by the analogue discount |
| **Capped confidence** | Hard cap (e.g., ≤ 0.45) regardless of evidence |
| **Monitor-only default** | No ACT state; only monitor, gather, CLARIFY |
| **Rule-based preference** | Prefer rules/benchmarks over statistical models that have no history to fit |

### 12.3 Unlock conditions (visible on the case file)
"Full analysis unlocks at week 13 with ≥ 2 complete POS audit cycles, or earlier if the analogue transfer is validated against the first 8 observed weeks." The KPI visibly *graduates* out of cold-start mode — a small, memorable product arc.

---

# 13. PERSONA INTELLIGENCE

The same KPI event is **not one insight**. It is a set of persona-specific decision briefs derived from the same structured conclusion object — different narrative depth, evidence visibility, recommended actions, risk emphasis, decision controls, and data visibility. This is the LLM's legitimate translation job, and it is also an entitlement boundary, not just a tone change.

| Persona | Primary question | Narrative | Evidence visibility | Actions & controls | Data visibility | Trust element |
|---|---|---|---|---|---|---|
| **Executive** (CEO/CFO/COO) | "What is the financial exposure and what decision is required?" | 5–7 lines: materiality, top driver, confidence, cost of waiting, decision required | Summary counts only ("12 supporting, 3 contradicting") with drill-in on demand | Approve/decline strategic decisions; escalate; see all options with rights status | Aggregates; no PII; no cost columns | Confidence state + cost-of-waiting prominently |
| **Analyst** | "What method, evidence, and calibration produced this?" | Full method dossier | Everything, with freshness, lineage, method per item | Challenge/correct: hypothesis verdicts, driver corrections, evidence ratings; **no approval rights** | All within own scope; PII masked | Decomposition math, per-stage method ledger, telemetry |
| **Operations / Supply Chain** | "Which SKU/site do I intervene on, and am I authorized?" | Operational playbook | Operational evidence (inventory, OSA, supplier comms) | Simulate and approve actions *within their authority*; escalate above limits | Own region rows (row-level); marketing/finance columns masked (column-level) | Decision-rights verdict per option ("AUTHORIZED" / "ESCALATE") |
| **KPI Owner / Data Steward** | "Is my contract right, and are my sources behaving?" | Contract health brief | Contract, lineage, source ledger, conflicts | Resolve definition conflicts; edit drivers/thresholds/rights; acknowledge contract gaps | Contract + lineage scope | Contract versioning and conflict routing |

**Product rule:** persona differences are *derived from* one conclusion object (same numbers, same ranks, same certainty state) — only depth, framing, evidence scope, action set, and channel differ. This is the difference between "role-based translation" and "different truths."

---

# 14. DECISION RECORD

The Decision Record is the signature ReasonFlow object — the unit of enterprise accountability.

### 14.1 Structure (PS schema extended)

| Field | Meaning |
|---|---|
| **Driver** | The ranked driver being addressed (evidence-backed, not assumed) |
| **Controllable lever** | The specific lever the business can pull (backup supplier, expedite, promotion) |
| **Action** | The concrete action, with scope (SKUs, DCs, duration) |
| **Expected impact** | Point estimate **plus range**, over a stated horizon ("+₹4.1M over 6 weeks, range +₹2.9M to +₹5.2M") |
| **Owner** | Named role + person accountable for execution |
| **Confidence** | Certainty state + composed confidence for *this option* |
| **Monitoring plan** | Metric, cadence, review window, success band ("daily WMS cover + weekly OSA; review day 14; success = within ±15% of predicted") |
| **Constraints checked** | Spend ceilings, lead-time limits, supply capacity, season constraints — each with pass/fail |
| **Decision rights verdict** | AUTHORIZED / ESCALATE (name the approver) / BLOCKED (reason) |
| **Evidence used** | The evidence set (supporting + contradicting) backing the driver |
| **Simulation version** | Which server-side simulation run the numbers came from |
| **Human decision** | Approve / Override / Reject — actor, role, comment, version, timestamp |
| **Actual outcome** | Recorded later (actual or explicitly simulated) |
| **Outcome variance** | Predicted vs actual, within-band? |
| **Reliability update** | How this outcome changed the calibration |

### 14.2 Why this beats a generic recommendation
A generic recommendation ("try a promotion") has no owner, no authority, no expected impact with range, no monitoring plan, and no outcome — it cannot be held accountable, so it isn't. The Decision Record converts advice into an **auditable enterprise asset**: who decided, on what evidence, with what expectation, and whether it worked. Ten thousand Decision Records are a decision-quality ledger an enterprise would pay to keep.

---

# 15. DECISION RIGHTS

Decision rights connect security to action. A recommendation never simply says "Do X" — every option carries an authority verdict computed from the contract.

### 15.1 The rights model (conceptual)
Each contract defines, per role: which action classes may be *recommended*, *simulated*, *approved*, up to which limits (₹ cost impact, spend ceilings, regional scope), and which require escalation to a named role.

### 15.2 Worked examples (demo)
| Persona | Option | Rights verdict |
|---|---|---|
| Supply Chain Manager (NE) | Activate backup supplier — cost impact ₹1.6M | **AUTHORIZED** — within ₹2M limit |
| Supply Chain Manager (NE) | Air-freight expedite — cost impact ₹3.4M | **ESCALATE → CFO** — option visible but locked for approval; simulation allowed |
| Analyst | Any option | **NO APPROVAL RIGHTS** — may simulate, challenge, correct; cannot approve |
| Executive (CFO) | Strategic budget shift (expedite) | **AUTHORIZED** — approves escalated option with audit |

### 15.3 Interaction with data visibility
Rights also bound *what the user may see while deciding*: row scope (own region), column scope (masked unit costs for non-finance roles), domain scope (finance data for finance roles). A user who cannot see the cost basis cannot approve the action it justifies — the system enforces both, and logs both.

**One line for the spec:** *the same recommendation object renders differently per persona — and may only be approved by those whose rights and visibility cover it.*

---

# 16. LEARNING & FEEDBACK

Learning is three layered mechanisms, all transparent and versioned. **This is not RLHF** — it is empirical, auditable recalibration.

### 16.1 Outcome learning (already in Round 1, kept)
Predicted impact vs actual outcome → mean absolute error, alignment rate, reliability **shrunk toward a prior when n is small** (one lucky hit cannot claim 100% reliability). Outcome records are visible on the case file.

### 16.2 Structured analyst/business-user feedback (new, required by PS objective 7)

| Feedback type | Captured as | Effect |
|---|---|---|
| Hypothesis verdict (correct / incorrect) | Per-case, per-hypothesis | Pattern reliability per hypothesis *class* → recalibrates future confidences for that class |
| Driver correction (re-attribute contribution) | Versioned edit to decomposition | Decomposition rule weights updated; template corrected |
| Evidence relevance rating | Per-evidence score | Retrieval scoring weights adjust (feature weights, not model retraining) |
| Recommendation usefulness | Per-option rating + comment | Decision template ranking — useful options surface first |
| Override reason | Required field on override | Stored with the decision; feeds template correction |
| Action outcome | Outcome record | Reliability update + monitoring-window defaults |

### 16.3 What feedback changes, concretely
- **Confidence calibration:** if "competitor promo" hypotheses are repeatedly marked incorrect, the class's baseline confidence is discounted — visibly, with the history shown.
- **Investigation templates:** accepted driver corrections become contract drivers (owner-approved), so the next case starts with better priors.
- **Recommendation reliability:** per-action-class reliability scores, shrunk by n.
- **Future case retrieval:** corrections re-weight memory similarity.
- **KPI contract evolution:** the contract is the sink for everything learned — new drivers, revised thresholds, updated expected ranges — with version history. **The contract gets smarter every cycle; that is the product's compounding loop made literal.**

### 16.4 Guardrails
All feedback is role-gated (analyst+ can correct; corrections are versioned), auditable, and visible ("confidence changed from 0.71 to 0.66 because 2 analysts marked this hypothesis class incorrect").

---

# 17. TRANSPARENCY LEDGER

The Transparency Ledger is a **visible product feature**, not an internal log. Every insight and every case carries it.

### 17.1 Per-stage ledger (example rows from the demo)

| Stage | Method | LLM? | Model | Latency | Tokens | Est. cost | Confidence impact | Sources |
|---|---|---|---|---|---|---|---|---|
| Detection | SQL + statistics (seasonal baseline, robust z) | No | — | 420 ms | — | — | sets baseline | 1 |
| Decomposition | SQL + business rules (price/volume/mix) | No | — | 310 ms | — | — | +0.10 | 2 |
| Hypothesis drafting | LLM (drafting, constrained by contract drivers) | Yes | small | 540 ms | 380 | ₹0.04 | — | — |
| Evidence gathering | Retrieval + rule scoring | No (extraction: small model) | — | 780 ms | 620 | ₹0.02 | +0.15 | 14 |
| Ranking & calibration | Rules + statistics + graph checks | No | — | 260 ms | — | — | +0.21 | — |
| Certainty state | Rules | No | — | 40 ms | — | — | — | — |
| Narrative (per persona) | LLM (translation from structured object) | Yes | small | 690 ms | 400 | ₹0.13 | — | — |
| **Total per insight** | — | **2 of 7 stages** | — | **~3.0 s** | **~1,400** | **≈ ₹0.19** | — | **14** |

### 17.2 Why it matters for enterprise deployment
- **The PS's core demand, answered visibly:** teams must show *when and why* they use deterministic logic, SQL, rules, statistics, ML, retrieval, or LLM — the ledger is that answer, live, not in a slide.
- **Cost governance:** cost per insight is a product number. Budget caps degrade gracefully to deterministic mode when exceeded — a CFO-facing control.
- **Trust:** "100% of the numbers on this screen were computed without an LLM" is a claim the ledger makes *verifiable*.
- **Drift monitoring:** per-stage latency/cost trends surface model and data drift operationally.

---

# 18. EVIDENCE & LINEAGE

The evidence chain is structural, not rhetorical:

```
Insight → Evidence Record → Source (document/row) → timestamp → freshness → lineage → analytical method
```

| Evidence state | Meaning | Handling |
|---|---|---|
| **Supporting** | Raises a hypothesis's support score | Counted with weight; openable |
| **Contradicting** | Lowers a hypothesis's support score | First-class, displayed beside supporting; drives abstention thresholds |
| **Stale** | Source older than its expected refresh cadence | Discounted weight; visibly flagged with the freshness gap |
| **Restricted** | Visible only to entitled roles | Contributes to reasoning for entitled roles; for others, counted as "n sources withheld" so confidence is **never silently inflated** |

**Rules that make lineage real:**
- No Evidence Record without a Source; no Source without timestamp, checksum, connector, and lineage.
- Every user-facing claim opens its evidence; every evidence opens its source document.
- Evidence scoping is always bounded (time window, region, product) — retrieval is never "the whole corpus."
- Narrative claims are rendered from the structured object; a claim without an evidence pointer cannot exist in the object, therefore cannot exist in the narrative.

---

# 19. ROUND 2 DEMO SCENARIO

**One scenario, one company, every official minimum expectation — the smallest story that proves the product.** FMCG remains the strongest demonstration because supply-chain cause-and-effect is instantly legible to any judge.

### 19.1 The company and data fabric

**Apex Foods** (continuity with Round 1's seeded scenario). Region: Northeast India. Category: instant noodles. Distribution: Guwahati DC. Ground truth is **simulated and known** (supplier delay + mid-quarter price increase), so the demo proves the engine recovers a pre-set truth — the honest way to demo "correctness."

**Three source systems, four connected KPIs:**

| KPI | Source | Cadence | Grain | Refresh state in demo |
|---|---|---|---|---|
| Revenue (invoiced) | ERP | Daily | SKU × DC | Current |
| Revenue (recognized) | Finance GL close | Monthly | Company × account | Current (period boundary differs) |
| On-Shelf Availability | POS retail audit | Weekly | Region × category | **6 days stale** |
| Inventory days-of-cover | WMS | Daily | SKU × DC | Current |
| Marketing ROI | ERP campaign module | Weekly | Campaign | Current (within plan — a contradiction source) |

### 19.2 The script (12–15 minutes, linear through one case file)

| # | Beat | Screen | What is proven |
|---|---|---|---|
| 1 | **Landing: materiality queue.** Revenue NE −12% (5.1σ) × ₹8.6M exposure → **CRITICAL**; Marketing ROI −4% (2.1σ) × ₹0.2M → WATCH; new SKU "Millet Noodles" flagged COLD START | Executive Overview | Detection ≠ materiality; triage; KPI portfolio |
| 2 | **Open Revenue NE case file → Contract tab.** Definition, formula, owner, drivers, thresholds, entitlements, decision rights — all versioned | KPI Contract | The governed object exists *before* any reasoning |
| 3 | **Reconcile tab — MOMENT 1.** ERP ₹84.0M vs Finance ₹87.0M: "Your inputs disagree." Definition conflict (invoiced vs recognized) + POS 6-day staleness → reliability 0.76 → confidence capped | Reconciliation | Heterogeneous sources *actually disagree* and the product detects and types the disagreement |
| 4 | **Investigation tab.** Decomposition: price +1.8%, volume −9.5%, mix −0.9%, residual −3.4% (all SQL-backed). Four competing hypotheses with support/contradict evidence side by side: supplier delay 0.82 / competitor promo 0.12 / marketing 0.04 / seasonal 0.02. Reasoning path graph shown. Certainty: ACT WITH CAUTION | Explain | Multi-factor movement; contribution analysis; competing hypotheses; evidence; lineage |
| 5 | **Persona switch (same case).** CEO brief (exposure, cost of waiting, decision required) → SC Manager playbook (SKU-level, Action A AUTHORIZED, Action B locked → ESCALATE CFO; marketing ROI column masked; South region rows invisible) → Analyst dossier (methods, contradictions, telemetry, feedback controls) | Persona intelligence + entitlements | Persona changes the answer/action; row/column security visible |
| 6 | **Decision Workspace.** Action A "activate backup supplier": slider simulates on server (+₹4.1M / 6 wks, range shown; cost +8%); Action B "air-freight expedite": faster but locked behind CFO rights. Approve A (version check, audit row). Monitoring plan attached: daily WMS + weekly OSA, review day 14 | Decide | Simulation server-side; decision rights; human approval; monitoring plan |
| 7 | **Fast-forward outcome.** Predicted +₹4.1M vs actual +₹3.9M → within band → reliability updated (shrunk, n small); case closed into memory | Learn | Outcome recording; calibration |
| 8 | **MOMENT 2 — Abstention case.** "Sales per outlet — South region": POS says OSA falling, ERP inventory healthy, POS 6 days stale, hypotheses tied 0.47/0.45 → **"Do not act yet."** + what would resolve it (refresh POS, confirm audit sample), routed to data owner, cost-of-waiting low | Abstention | The abstention state machine, fully |
| 9 | **Sparse-history case.** "Millet Noodles" (5 weeks): cold-start mode — 3 named sibling analogues, benchmark bands, wide CI, confidence capped 0.45, monitor-only, unlock conditions shown | Sparse history | Cold-start behavior, no fabricated confidence |
| 10 | **Feedback.** Analyst marks "competitor promo" hypothesis incorrect + rates evidence → confidence for that class visibly recalibrates (0.12 → 0.07 pattern prior) | Learning | Structured feedback loop |
| 11 | **Memory.** "Similar to NE Q3 2025 case (similarity 0.87): same supplier, same DC; outcome was +₹3.1M within band" | Memory | Institutional memory with written similarity |
| 12 | **MOMENT 3 — Transparency Ledger close.** Per-stage method/LLM/latency/token/cost table; "100% of numbers computed without an LLM; 2 of 7 stages used one; total intelligence cost ₹0.19 vs ~₹2,000 of analyst time" | Transparency | LLM/non-LLM breakdown + telemetry + cost per insight |

**Coverage check:** 4 connected KPIs ✓ · 3 heterogeneous sources ✓ · different grains ✓ · different cadences ✓ · multi-factor movement ✓ · KPI contract ✓ · reconciliation conflict ✓ · materiality ✓ · decomposition ✓ · competing hypotheses ✓ · evidence ✓ · persona outputs ✓ · high-confidence case ✓ (ACT WITH CAUTION + decision) · abstention case ✓ · sparse-history case ✓ · entitlement scenario ✓ · action recommendation ✓ · decision rights ✓ · simulation ✓ · human approval ✓ · outcome ✓ · feedback ✓ · memory ✓ · telemetry ✓ · LLM/non-LLM breakdown ✓. **Every official minimum expectation, in one story.**

---

# 20. CRITICAL DEMO MOMENTS

**Moment 1 — Reconciliation: "Your inputs disagree."**
ERP says ₹84M, Finance says ₹87M. ReasonFlow does **not** proceed to explain the movement. It stops, shows the two numbers, names the mismatch type (definition + calendar), shows the confidence impact (−0.12), and routes the conflict to the KPI owner — while offering the justified working value. *The judge learns: this product reasons about the reliability of its inputs before reasoning about the business. Nothing on the market does this visibly.*

**Moment 2 — Abstention: "Do not act yet."**
Contradictory, stale evidence with statistically tied hypotheses. The screen refuses to offer actions, names exactly what data would settle it, names who should provide it, and prices the cost of waiting vs acting. *The judge learns: this product's honesty is a feature, not a disclaimer — and it is exactly what the PS demands ("abstains when evidence is insufficient or contradictory").*

**Moment 3 — The Transparency Ledger: "Every number here was computed without an LLM."**
The per-stage method table with latency, tokens, and cost — closing on "2 of 7 stages used an LLM; total intelligence cost ₹0.19 vs ~₹2,000 of analyst time." *The judge learns: the LLM is a metered, optional, labeled translator — never the source of quantitative truth. This is the single most contest-winning screen because it converts the PS's hardest demand into a live artifact.*

---

# 21. PRODUCT INFORMATION ARCHITECTURE

Conceptual application structure — areas, purposes, users, information, actions. (No technical architecture decisions here.)

| Area | Purpose | Primary user | Key information | Key actions |
|---|---|---|---|---|
| **Executive Overview** | Materiality-prioritized attention queue; portfolio health | Executive | CRITICAL/ELEVATED/WATCH queue with ₹ exposure, confidence state, decisions awaiting approval | Drill into case file; approve/decline escalated decisions |
| **KPI Intelligence** | The contract portfolio; every KPI as a governed object | KPI owner, analyst | KPI list with states (ACTIVE/CONFLICTED/COLD START), current values, open cases | Create/edit contracts; view case files |
| **KPI Contract** | The governed definition | KPI owner, data steward | Definition, formula, lineage, cadences, drivers, thresholds, materiality rules, entitlements, decision rights, versions | Edit (versioned), resolve conflicts, adjust rights/thresholds |
| **Reconciliation** | Input-reliability intelligence | Analyst, KPI owner, data owner | Source ledger, conflicts, freshness profile, working values with justification | Resolve/route conflicts; refresh sources; accept working value |
| **Investigation / Reasoning** | The EXPLAIN stage of a movement | Analyst (deep), exec/ops (narrative) | Decomposition, ranked hypotheses, support/contradict evidence, reasoning paths, certainty state, confidence composition | Challenge/correct; rate evidence; escalate to decision |
| **Decision Workspace** | The DECIDE stage | Operations/SC (approve within rights), exec (escalations) | Options with driver→lever→action→impact→owner→confidence→monitoring; rights verdicts; simulations; approval history | Simulate; approve/override/reject; attach monitoring plan |
| **Evidence & Lineage** | The traceability chain | Analyst, auditor | Every Evidence Record → Source → timestamp → freshness → lineage → method | Open sources; mark stale/restricted; rate relevance |
| **Institutional Memory** | Compounding decision memory | All (scoped) | Past cases, similarity explanations, outcomes, reliability history | Retrieve; link cases; correct memory entries |
| **Governance & Transparency** | Trust surfaces | Exec, analyst, data steward | Transparency Ledger (methods/LLM/cost per stage), telemetry, audit log, feedback log, calibration history | Set cost caps; review drift; audit |

**Navigation philosophy:** everything is reachable from the KPI Case File (the product's spine) and the Executive Overview (the product's front door). Queues, not walls of charts.

---

# 22. OLD REASONFLOW → ROUND 2 REASONFLOW MAPPING

| Old element | Verdict | Round 2 form |
|---|---|---|
| Executive dashboard (persisted detections) | **CHANGE** | Executive Overview: materiality queue + portfolio health (same persisted-detection core) |
| Investigation workspace (stage stepper) | **CHANGE** | Investigation tab inside the KPI Case File; stepper becomes lifecycle states (CONTRACT→…→LEARN) |
| KPI monitor (observations, formula, method, source) | **KEEP** | Absorbed into the KPI Case File + Contract tab |
| Knowledge graph page + constellation | **DEMOTE → REUSE AS ENGINE** | No product page; graph drives driver maps and reasoning paths behind hypotheses |
| Evidence center | **KEEP** | Enhanced: freshness, stale/restricted states, relevance ratings |
| Decision Lab (sliders → server simulation, 409) | **CHANGE** | Decision Workspace: + decision rights, owners, constraints, monitoring plans |
| Institutional memory (embedding + filters + similarity) | **KEEP** | Decision memory; feeds cold-start analogues and pattern reliability |
| Alerts (acknowledge) | **CHANGE** | Materiality-triage queue; acknowledgment becomes case opening/closing |
| Multi-agent workflow (LangGraph) | **KEEP (reframed)** | Staged grounded pipeline; LLM stages labeled per Transparency Ledger — headline is the *staging*, not "agents" |
| Deterministic detection (seasonal baseline, robust z, CI, versions) | **KEEP** | DETECT stage, unchanged core; feeds materiality |
| Deterministic fallback / `llm_mode` | **KEEP** | Promoted to Transparency Ledger + cost-cap degradation |
| Simulation engine (equation-based, server-side) | **KEEP** | Decision Workspace simulation, versioned |
| Outcome recording + shrunk reliability | **KEEP** | LEARN stage, extended with structured feedback |
| Entity resolution (aliases → canonical) | **KEEP** | Inside reconciliation (hierarchy/entity mismatch) |
| Authentication, RBAC, multi-tenancy, rate limits, audit | **KEEP** | Foundation for data-level entitlements (row/column/domain); demo pre-provisioned |
| Hypothesis agent + evidence agents + arbiter + narrative agent | **CHANGE** | Same roles, re-labeled as *stages with methods* (hypothesis drafting / gathering & scoring / ranking & certainty / narrative translation) |
| Business Knowledge Graph (SQL, Neo4j optional) | **REUSE AS ENGINE** | Internal machinery only |
| External news/social feeds | **REMOVE** | Roadmap note only |
| Early-warning risk models ("78% probability of decline in 30 days") | **REMOVE** | Roadmap note only |
| Industry-agnostic `InvestigationConfig` | **KEEP** | KPI Contracts + industry templates by configuration (2–3 demo configs, not 7) |
| Landing page, signup, join-by-slug, invite flows | **DEMOTE** | Exist in the codebase; never demoed — Round 2 demo starts inside a pre-provisioned Apex Foods workspace |
| Visual constellation / animation layer | **REMOVE** | Restrained motion only; animation is no longer a feature |
| Confidence score (single number) | **CHANGE** | Certainty state machine (ACT / CAUTION / CLARIFY / ABSTAIN) + composed confidence with visible factors |
| Comments on investigations | **DEMOTE** | Approval comments and feedback survive; free-form collaboration threads are out of demo scope |
| Health/admin screens, command palette, themes | **DEMOTE** | Behind the scenes; not demo surface |
| "CausalPulse Nexus" name / causal branding | **REMOVE** | ReasonFlow; "evidence-backed ranking," never "causal proof" |

---

# 23. WHAT WE REMOVE

1. **CausalPulse Nexus name and all causal-inference branding** (the honest hedging "evidence-backed, not proven causal" stays; the word "causal" leaves product surfaces).
2. **Knowledge-graph visualization as a product surface** (stays as engine machinery).
3. **External news/social/competitor-pricing feeds** as a capability (roadmap only — noisy, costly, legally messy, and not what Round 2 asks).
4. **Early-warning risk models** (roadmap only — unrequired, demo-risky, maintenance-heavy).
5. **Landing page, signup, onboarding, invitation flows as demo surfaces.**
6. **The animation/constellation layer as product value.**
7. **Free-form collaboration threads** (approval comments and structured feedback remain).
8. **The "multi-agent platform" as the headline framing** — replaced by "staged, method-labeled pipeline" (agents are implementation; staging and labels are the product truth).

---

# 24. WHAT WE ADD

*(Each addition exists because the Round 2 PS demands it or the concept requires it.)*

1. **KPI Contract** (PS: semantic contract — definitions, calculations, drivers, thresholds, lineage, access) — the new center of gravity. §7.
2. **Reconciliation Intelligence** (PS: heterogeneous-source reconciliation) — source ledger, conflict typing, freshness scoring, reliability caps. §8.
3. **Materiality Intelligence** (PS: "materiality based on both statistical significance and business impact") — significance × exposure triage. §9.
4. **Contribution Analysis** (PS: "multiple interacting drivers such as price, volume, mix") — deterministic decomposition as the quantitative spine. §10.
5. **Certainty State Machine + Abstention** (PS: "communicates uncertainty and abstains") — ACT / CAUTION / CLARIFY / ABSTAIN with clarification requests. §11.
6. **Sparse-History / Cold-Start Mode** (PS: "sparse history for new products, categories or markets") — analogues, benchmarks, caps, unlock conditions. §12.
7. **Persona Intelligence** (PS: "persona-specific narratives… role-based personalization") — one conclusion object, four decision briefs. §13.
8. **Decision Record** (PS: the action schema) — driver → lever → action → impact → owner → confidence → monitoring plan, extended. §14.
9. **Decision Rights** (PS: "business levers, constraints and decision rights") — authority verdicts bound to entitlements. §15.
10. **Structured Feedback** (PS: "mechanism to learn from analyst and business-user feedback") — hypothesis verdicts, corrections, ratings, overrides. §16.
11. **Transparency Ledger + Runtime Telemetry** (PS: LLM/non-LLM breakdown; latency, model calls, tokens, cost) — live, per-stage. §17.
12. **Data-Level Entitlements** (PS: "row-, column- and domain-level security") — region rows, masked columns, domain scopes, audited. §15.3.

---

# 25. WHAT WE EXPLICITLY DO NOT BUILD

The prototype is **depth over breadth**. Excluded from Round 2:

1. **Live enterprise integrations** — all sources are simulated/seed data with realistic cadences and grains. Real connectors are a post-round roadmap item, not prototype work.
2. **External data pipelines** — no news, social, or market feeds.
3. **A chatbot interface** — no conversational analysis surface, no NL-to-SQL. Persona briefs are structured pages, not chat.
4. **Microservices / event-streaming infrastructure** — one coherent platform; the pipeline is stateless-per-case by design.
5. **Production MLOps** — no model registries, training pipelines, or auto-retraining. All models are simple, versioned, and deterministic enough to explain.
6. **Advanced forecasting research** — seasonal baselines + CIs are sufficient; no deep learning forecasters.
7. **Excessive industry breadth** — 2–3 configured industries (FMCG primary; one secondary, e.g., Retail) to *prove* configuration-driven design, not 7 half-baked ones.
8. **Decorative graph pages, animation showcases, or design-system polish beyond coherence.**
9. **Collaboration systems** — no chat, threads, or notification centers beyond approval/feedback.
10. **Admin sprawl** — user management exists but is not demo surface; no billing, no SSO federation, no org-provisioning wizard.
11. **Auto-execution of anything** — the human approval gate is absolute and demoed as such.
12. **Digital-twin-grade simulation** — equation-based, costed, versioned projections only.
13. **LLM fine-tuning or custom models** — small, cheap, hosted models only, with deterministic fallback always live.

---

# 26. OFFICIAL ROUND 2 REQUIREMENT COVERAGE MATRIX

| Official requirement (Track 3) | Where the product delivers | Where the demo proves it |
|---|---|---|
| **Objective 1** — Detect and prioritise material KPI movements | DETECT (statistics) + TRIAGE (significance × ₹/margin/strategy) | Beat 1: Revenue NE CRITICAL vs Marketing ROI WATCH |
| **Objective 2** — Reconcile data and business context across heterogeneous sources | Reconciliation Intelligence: source ledger, conflict typing, freshness, entity/calendar/grain normalization | Beat 3 / Moment 1: ERP ₹84M vs Finance ₹87M + stale POS |
| **Objective 3** — Identify and rank explanatory drivers using appropriate analytical methods | EXPLAIN: SQL decomposition + competing hypotheses + retrieval scoring + graph checks + calibration | Beat 4: price/volume/mix waterfall; 4 ranked hypotheses |
| **Objective 4** — Persona-specific narratives supported by traceable evidence | Persona Intelligence derived from one structured conclusion object | Beat 5: CEO brief / SC playbook / analyst dossier, same case |
| **Objective 5** — Communicate uncertainty and abstain when evidence insufficient or contradictory | Certainty state machine: ACT / CAUTION / CLARIFY / ABSTAIN with clarification requests | Beat 8 / Moment 2: South region abstention |
| **Objective 6** — Recommend practical actions grounded in business levers, constraints and decision rights | Decision Record + Decision Rights: schema'd options, constraints checked, AUTHORIZED/ESCALATE verdicts | Beats 5–6: backup supplier authorized; air freight escalated to CFO |
| **Objective 7** — Mechanism to learn from analyst and business-user feedback | Structured feedback + outcome calibration + contract evolution | Beats 7 & 10: outcome variance; hypothesis marked wrong → visible recalibration |
| **Objective 8** — Operate within realistic security, cost, latency and scalability constraints | Tenancy + entitlements + cost caps + telemetry + config-driven industries + stateless per-case pipeline | Beats 5 (entitlements) & 12 (telemetry); ledger shows ₹0.19/insight |
| **Complexity** — Multiple interacting drivers (price, volume, mix, marketing, supply, seasonality…) | Decomposition + multi-hypothesis scoring | Beat 4 (price + supply + seasonal interplay) |
| **Complexity** — Different refresh cadences, grains, quality, coverage | Reconciliation ledger with per-source profiles | Beat 3 (daily/weekly/monthly; SKU×DC vs region×category) |
| **Complexity** — Inconsistent KPI definitions, hierarchies, calendars, rules | Contract versioning + conflict routing + canonical entities | Beat 3 (invoiced vs recognized; calendar note) |
| **Complexity** — Sparse history for new products/categories/markets | Cold-start mode | Beat 9: Millet Noodles, analogues, cap 0.45 |
| **Complexity** — Materiality = statistical significance AND business impact | Materiality Intelligence | Beat 1 |
| **Complexity** — Contradictory evidence, missing data, confidence calibration | Contradiction as first-class; calibration shrunk by n | Beats 4, 7, 8 |
| **Complexity** — Role-based personalization of depth, actions, channels | Persona Intelligence | Beat 5 |
| **Complexity** — Row-, column-, domain-level security; auditability | Data-level entitlements + audit | Beat 5 (masked columns, region rows) |
| **Complexity** — Model/data drift, feedback capture, continuous evaluation | Telemetry trends + feedback log + calibration history | Beats 10, 12 |
| **Complexity** — LLM economics: model choice, tokens, latency, caching, cost per insight | Transparency Ledger + cost caps + small-model routing | Beat 12 / Moment 3 |
| **Core rule** — LLM not the source of quantitative truth; show when/why each method is used | Two-layer split + per-stage method ledger | Moment 3: "100% of numbers without LLM" |
| **Minimum** — 3–5 connected KPIs, 2–3 sources, different grains/cadences | Demo fabric (4 KPIs, 3 sources) | Whole scenario |
| **Minimum** — Lightweight KPI/semantic contract (definitions, calculations, drivers, thresholds, lineage, access) | KPI Contract object | Beat 2 |
| **Minimum** — ≥2 personas with different narratives/actions | Persona Intelligence | Beat 5 |
| **Minimum** — One multi-factor movement with known/simulated drivers | Simulated ground truth (supplier delay + price) | Beat 4 |
| **Minimum** — One low-confidence scenario: clarification or abstention | Abstention state + clarification request | Beat 8 / Moment 2 |
| **Minimum** — One sparse-history / newly launched KPI scenario | Cold-start mode | Beat 9 |
| **Minimum** — One role-based security/entitlement scenario | Row/column/domain masking | Beat 5 |
| **Minimum** — Evidence with source freshness, analytical method, contribution, confidence, lineage | Evidence chain + ledger | Beats 3–4, 12 |
| **Minimum** — Clear LLM vs non-LLM breakdown | Transparency Ledger | Beat 12 / Moment 3 |
| **Minimum** — Runtime telemetry: latency, model calls, tokens, estimated cost | Live telemetry panel | Beat 12 / Moment 3 |

---

# 27. JUDGE QUESTIONS & DEFENSES

| Question | Defense |
|---|---|
| **Why not Power BI + Copilot?** | Copilot narrates a chart from one platform's already-modeled data, with the LLM as the narrator of numbers it did not compute — the anti-pattern your brief forbids. It has no KPI contract with entitlements and decision rights, no cross-source reconciliation, no competing hypotheses with contradicting evidence, no abstention, no decision records with owners and monitoring plans, no outcome-calibrated confidence, and no memory of whether a past recommendation worked. We don't replace BI — we sit on top of whatever sources exist and own the layer BI explicitly leaves unowned: interpretation → reconciliation → alignment → decision. |
| **Why not Tableau + AI?** | Same category answer: visualization answers "what"; ReasonFlow governs "what it means, how reliable the picture is, who may act, and whether the action worked." Tableau's AI summarizes one view; it cannot adjudicate two disagreeing systems, gate an action by decision rights, or calibrate confidence against the outcomes of past decisions. |
| **Why not just a semantic layer?** | Semantic layers govern *definitions and lineage* and stop there. They carry no drivers, no uncertainty, no entitlements bound to actions, no decision records, no outcomes, no memory. ReasonFlow's contract is a *decision-lifecycle* object — the semantic layer is one tab of it. We are complementary: a mature semantic layer could even feed our contract. |
| **Why not a data-quality platform?** | Data-quality tools answer "is the data clean?" — a property of pipelines. We answer "given how these sources disagree *today*, what is true enough to act on, for whom?" Reconciliation is a stage in a decision loop; when we flag a conflict, we show its *decision impact* (confidence, abstention, cost of waiting) — not a DQ scorecard. |
| **Why not a chatbot over SQL?** | Chat-over-SQL answers "what" in fluent prose, on one model, with no reconciliation, no competing hypotheses, no evidence chain, no decision rights, no outcomes, and the LLM as the source of numeric truth — the exact failure mode the brief prohibits. And when inputs conflict, a chatbot averages them into confident prose; we stop and say so. |
| **Why does the LLM need to exist?** | Three labeled jobs: drafting hypotheses constrained by the contract, extracting claims from evidence text, and translating the structured conclusion into persona briefs. Zero jobs involving numbers. Kill the LLM and the pipeline still runs deterministic — we demo the fallback. Its economic case is in the ledger: ₹0.19 of model cost per insight against ~₹2,000 of analyst time. |
| **What happens if data conflicts?** | That is a designed input, not an edge case. Reconciliation types the conflict (definition, refresh, grain, hierarchy, calendar), shows both numbers, caps confidence, routes the conflict to its owner, and proceeds only on an explicitly justified working value — never a silent merge. Moment 1 of the demo is exactly this. |
| **What happens if history is insufficient?** | Cold-start mode: sibling-analogue borrowing with a visible discount, benchmark bands, wide intervals, capped confidence, monitor-only default, and explicit unlock conditions. The system behaves differently under sparse history — it does not just print a lower number. Demoed with the new SKU. |
| **How do you prevent hallucinations?** | Structurally: no claim without an Evidence Record; no Evidence Record without a Source (timestamp, checksum, lineage); narratives rendered from a structured conclusion object the LLM cannot alter; every number computed by a labeled deterministic method; the whole pipeline runs without the LLM if needed. Hallucination is not "prompted away" — it is designed out. |
| **How does this create measurable business value?** | Four hard numbers, all demoed: (1) decision cycle time — from ~5 working days of reconciliation and alignment to the same day, on one shared decision context; (2) contradiction cost — contradictory cross-team actions are eliminated by construction (one contract, one evidence record, rights-checked actions); (3) repeat-analysis cost — decision memory retrieves the last similar case instead of re-litigating it; (4) cost per insight — ₹0.19 vs ~₹2,000 of analyst time (~10,000×), shown live. Plus the compounding asset: every recorded decision improves future calibration. |
| **Why is this scalable?** | Contracts and industry templates are configuration, not code (our engine already runs multiple industries from one codebase). The pipeline is stateless per case — concurrent cases across KPIs/regions are independent. Every object is tenant-scoped, and entitlements are contract-level, so a new region or KPI is data, not engineering. We claim this honestly as a prototype with a phased enterprise roadmap — not hand-waving. |
| **Why would an enterprise adopt it?** | Because it doesn't ask for migration (it sits alongside the stack), it addresses the cost they already feel (reconciliation meetings, contradictory actions, repeated analysis), it gives them assets they currently lack (decision records, decision memory, calibrated confidence), and its trust surfaces (abstention, ledger, entitlements, audit) satisfy the controls that gate enterprise AI adoption. |
| **What makes this innovative?** | The category claim: nobody owns the layer between BI insight and ERP execution. Three things are new as a *product*: (1) the KPI contract that carries decisions and outcomes, not just definitions; (2) reconciliation-before-reasoning — input reliability scored before business reasoning; (3) the Decision Record as a compounding enterprise asset. Plus abstention as a designed product state. The innovation is a governance-and-workflow framing of an unsolved business problem, not a new model. |
| **What is proprietary/defensible?** | Not a model and not a prompt: the object schemas (contract, evidence, decision record), the certainty state machine, the outcome-calibration economics, and the compounding memory. Defensibility grows with usage — every recorded decision raises switching cost. |

---

# 28. PRODUCT-LEVEL ACCEPTANCE CRITERIA

Each criterion is testable in the demo; all 17 must pass.

| # | The prototype must prove that… | Proven when (demo check) |
|---|---|---|
| 1 | **The KPI is governed before reasoning** | The Revenue NE case file opens on its Contract tab; no investigation exists without a contract |
| 2 | **Heterogeneous sources can disagree** | ERP ₹84.0M vs Finance ₹87.0M shown side by side |
| 3 | **ReasonFlow detects the disagreement** | Reconciliation verdict CONFLICTED, mismatch typed, confidence impact shown |
| 4 | **Materiality is calculated** | Queue shows Revenue NE CRITICAL and Marketing ROI WATCH with the significance × impact arithmetic visible |
| 5 | **Quantitative reasoning happens without the LLM** | Decomposition figures clickable to SQL/rule computations; ledger shows "LLM: No" on every numeric stage |
| 6 | **Multiple hypotheses compete** | Four hypotheses ranked, not one answer |
| 7 | **Evidence supports and contradicts them** | Support/contradict columns populated with openable sources on every hypothesis |
| 8 | **The system can abstain** | South region case shows "Do not act yet" with named missing data, routed owner, cost-of-waiting |
| 9 | **Persona changes the answer/action** | Same case: CEO brief ≠ SC playbook ≠ analyst dossier; SC sees AUTHORIZED/ESCALATE, analyst sees methods and no approve button |
| 10 | **Decision rights matter** | Action B (₹3.4M) visibly locked for SC, escalated to CFO; Action A (₹1.6M) authorized |
| 11 | **The recommended action is structured** | Option card shows driver → lever → action → impact+range → owner → confidence → monitoring plan |
| 12 | **Simulation is interactive** | Moving the slider re-simulates on the server and updates expected impact + version |
| 13 | **A human approves** | Approval row records actor, role, version, comment, timestamp; nothing executes without it |
| 14 | **An outcome is recorded** | Fast-forward: predicted +₹4.1M vs actual +₹3.9M, within band, visible on the case |
| 15 | **Feedback is captured** | Analyst marks a hypothesis incorrect; the class's pattern prior visibly changes |
| 16 | **Memory retrieves previous cases** | "Similar to NE Q3 2025 (0.87)" retrieved with written similarity explanation |
| 17 | **Telemetry is visible** | Ledger shows per-stage method, LLM usage, latency, tokens, cost; total ₹0.19/insight |

---

# 29. FINAL ONE-PAGE PRODUCT SUMMARY

**ReasonFlow — Governed KPI-to-Decision Platform.**
*"Where KPI movements become governed decisions."*

Enterprises run on KPIs, but the most expensive layer of the modern enterprise — between a KPI moving and a decision being made — is unowned. Interpretations drift, systems disagree, actions contradict, and decisions are forgotten. **ReasonFlow owns that middle.** Every important KPI becomes a **KPI Contract**: a governed business object carrying definition, formula, owner, sources, lineage, drivers, thresholds, materiality rules, entitlements, and decision rights. Before any movement is analyzed, **Reconciliation Intelligence** verifies the reliability of the picture itself — conflicting sources, stale feeds, mismatched grains and calendars are surfaced, typed, and priced in confidence, never silently merged. Material movements are triaged by **materiality** (statistical significance × business impact), decomposed deterministically (price/volume/mix), and explained through **competing hypotheses scored on supporting and contradicting evidence**, each claim traceable to an openable source. When evidence is insufficient or contradictory, ReasonFlow **abstains** — "do not act yet" — and names exactly what data would settle the question. When it can act, it produces a **Decision Record**: driver → controllable lever → action → expected impact → owner → confidence → monitoring plan — simulated on the server, gated by **decision rights**, translated into **persona-specific briefs** for executives, analysts, and operators, and approved by a human. Every decided case is outcome-tracked, recalibrates the system's confidence, and compounds into **decision memory**, so the next similar movement is recognized and decided faster and cheaper. **The LLM never computes a number** — it is a labeled, metered translator — and the **Transparency Ledger** proves it stage by stage, down to ₹0.19 per insight. *BI ends at insight. ERP begins at execution. ReasonFlow owns the governed middle.*

---

*End of Phase 1 — Product Specification. This document is the complete, unambiguous product definition for Phase 2 (architecture, data model, tech stack) and Phase 3 (prototype implementation). The demo scenario in §19 and the acceptance criteria in §28 are the binding acceptance tests.*
