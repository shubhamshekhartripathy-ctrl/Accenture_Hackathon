# UI/UX AUDIT — ReasonFlow Round 2

## Overview
This audit maps the current frontend implementation against the authoritative `REASONFLOW_ROUND2_PRODUCT_SPEC.md` and `REASONFLOW_ROUND2_ARCHITECTURE (3).md`.

**CRITICAL FINDING:** The backend architecture (S1-S12) is 100% complete. There are **zero missing API integrations** and **zero backend modifications required**. Every required endpoint exists and returns real, deterministic data. However, the frontend has structural misplacements (UI components stuffed into the wrong tabs) and missing polish/design system application.

---

## 1. AC1–AC26 UI Mapping

| Acceptance Criteria | Status in UI | Component | Notes |
|---|---|---|---|
| **AC1: KPI governed before reasoning** | Fully Real | `CaseFileContract.tsx` | Contract renders correctly with gaps/status. |
| **AC2-AC3: Disagreement detected & typed** | Fully Real | `CaseFileReconcile.tsx` | Conflict cards, freshness, and reliability rendered accurately. |
| **AC4: Materiality calculated** | Fully Real | `Overview.tsx` | Queue prioritizes correctly, drill-down arithmetic is fully wired. |
| **AC5-AC7: Quantitative explanation & hypotheses** | Fully Real | `CaseFileInvestigation.tsx` | Decomposition, hypotheses, and evidence render perfectly. |
| **AC8: Abstention** | Fully Real | `CaseFileInvestigation.tsx` | Abstention state machine is fully wired with all 6 required fields. |
| **AC9-AC10: Persona intelligence & Rights** | Fully Real | `BriefCard` | Rendered correctly based on active persona. |
| **AC11-AC13: Structured action, simulation, approval** | Partially Wired (Misplaced) | `OptionsPanel` | **UI Misplacement:** Rendered inside Investigation tab, while the "Decisions" tab shows a Placeholder. |
| **AC14-AC16: Outcomes, feedback, memory** | Partially Wired (Misplaced) | `MemoryPanel`, `OutcomeControls` | **UI Misplacement:** Rendered inside Investigation tab, while the "History" tab shows a Placeholder. |
| **AC17: Telemetry visible** | Fully Real | `Transparency.tsx` | Full ledger rendered perfectly. |
| **AC18: Multiple business scenarios** | Fully Real | `Scenarios.tsx` | Start flow wired and functional. |
| **AC19: Guardrails** | Fully Real (Misplaced) | `OptionsPanel` | Rendered correctly but in the wrong tab. |
| **AC20: Second-order impacts** | Fully Real (Misplaced) | `SecondOrderChain` | Rendered correctly but in the wrong tab. |
| **AC21: Decision collisions** | Fully Real (Misplaced) | `ResolveControls` | Collision banners render correctly but in the wrong tab. |
| **AC22: Decision Portfolio** | Fully Real | `PortfolioCard` | Renders correctly on Overview page. |
| **AC23: Contract proposals** | Fully Real (Misplaced) | `ProposalsPanel` | Rendered correctly but in the wrong tab (should be in History). |
| **AC24: LLM Routing** | Fully Real | `Transparency.tsx` | Route reasons mapped and rendered. |
| **AC25: Memory pgvector retrieval** | Fully Real (Misplaced) | `MemoryPanel` | Works perfectly but placed in the wrong tab. |
| **AC26: Semantic cache** | Fully Real | `Transparency.tsx` | Cache hits and cost avoided are visible. |

---

## 2. Placeholder / Fake UI Elements
- **No fake data:** All data in the app is real and derived from the backend APIs.
- **Placeholders in `CaseFile.tsx`:** The `decisions` and `history` tabs currently render a `<Placeholder />` component indicating they belong to S7 and S9.
  - *Irony:* S7 and S9 are actually fully implemented on the backend AND frontend, but their UI components (`OptionsPanel`, `OutcomeControls`, `MemoryPanel`, `ProposalsPanel`) were dumped at the bottom of `CaseFileInvestigation.tsx` instead of being moved to their respective tabs.

---

## 3. Dead / Disabled Interactions
- **DemoBar Actions:** `Inject POS error`, `Fast-forward 14d`, and `Reset DB` in `DemoBar.tsx` might still be tagged as placeholders for final polish, despite the backend endpoints (`/demo/inject-pos`, `/demo/fast-forward`, `/demo/reset`) being completely functional (per S12). 

---

## 4. Missing API Integrations
- **NONE.** The backend is 100% complete and serves all required data.

---

## 5. Visual / UI Issues
- **Unstyled / Basic Layouts:** The UI lacks the requested "premium design aesthetics" (vibrant colors, dark modes, glassmorphism, smooth gradients, micro-animations, typography like Inter/Outfit).
- **Poor Information Architecture:** The `CaseFileInvestigation.tsx` file is massively bloated (785 lines) because it absorbs the UI for Decisions (S7) and History (S9) which should have been split into `CaseFileDecisions.tsx` and `CaseFileHistory.tsx`.

---

## 6. Exact Files to Modify

**Frontend:**
- `src/pages/CaseFile.tsx` (Re-route tabs to actual components instead of placeholders).
- `src/pages/CaseFileInvestigation.tsx` (Extract Decisions and History components out to shrink file size).
- `src/pages/CaseFileDecisions.tsx` (New file, containing `OptionsPanel`, `ResolveControls`, `SecondOrderChain`, `OutcomeControls`).
- `src/pages/CaseFileHistory.tsx` (New file, containing `MemoryPanel`, `ProposalsPanel`).
- `src/components/DemoBar.tsx` (Wire the buttons to the actual `/demo/*` API endpoints).
- `src/styles/tokens.css` & `tailwind.config.ts` (Implement premium design tokens, typography, glassmorphism).
- `index.css` (Base styling and animations).

**Backend:**
- **NONE.**

---

## 7. Risks to S1–S12
- **Zero Risk to Backend:** Since no backend files will be touched, S1-S12 logic remains perfectly intact.
- **Frontend Refactoring Risk:** Moving components out of `CaseFileInvestigation.tsx` requires careful prop drilling or API re-fetching setup to ensure state is maintained. We must ensure the `api.get` calls are preserved in the newly separated tab components.

---

## Proposed Implementation Phases

**Phase 1: Structural Refactoring**
Extract `OptionsPanel`, `MemoryPanel`, and `ProposalsPanel` from `CaseFileInvestigation.tsx`. Create `CaseFileDecisions.tsx` and `CaseFileHistory.tsx`. Wire `CaseFile.tsx` tabs to use these new components instead of Placeholders.

**Phase 2: DemoBar Wiring**
Connect the DemoBar actions to the existing backend endpoints to fully enable the E2E demo capabilities.

**Phase 3: Premium UI / Aesthetics**
Implement modern design principles (glassmorphism, smooth transitions, premium typography, harmonic color palettes) across all major screens (Overview, Case File tabs) to achieve the requested "WOW" factor.
