/** Shared API payload types. */

export interface KpiRow {
  id: string;
  code: string;
  name: string;
  category: string;
  region: string;
  unit: string;
  contract: { id: string; name: string; status: string; version: number; chip: string } | null;
}

export interface QueueEntry {
  kpi_id: string;
  kpi_code: string;
  kpi_name: string;
  region: string;
  unit: string;
  band: string;
  score: number | null;
  deviation_pct: number;
  robust_z: number;
  current_value: number;
  baseline: number;
  ci: [number, number];
  exposure_rs: number | null;
  cold_start: boolean;
  monitor_only: boolean;
  arithmetic: Record<string, unknown> | null;
  detection_method: string;
  model_version: string;
  detected_at: string | null;
  contract_status: string | null;
  contract_id: string | null;
  investigation_id: string | null;
  workflow_state: string | null;
  reliability: number | null;
}


export interface EvidenceLink {
  doc_key: string; title: string; state: string; weight: number; source: string | null;
  data_classification: string | null; freshness: number | null; lineage: string | null;
  summary: string | null; access_roles: string[];
}

export interface Hypothesis {
  id: string; code: string; statement: string; pattern_class: string; rank: number; status: string;
  support_mass: number; contradiction_mass: number; balance: number; freshness_avg: number;
  source_agreement: number; pattern_prior: number; confidence: number; final_confidence: number;
  evidence_counts: Record<string, number>; reasoning_path: string[]; evidence: EvidenceLink[];
}

export interface DecompComponent { component: string; value: number; pct: number; method: string; query_ref: string; detail: string | null; }

export interface Investigation {
  id: string; workflow_state: string; contract_version: number; period_key: string;
  reliability: number | null; confidence_cap: number | null; working_value: number | null;
  cold_start_mode: boolean; last_error: string | null;
  kpi: { code: string; name: string; unit: string } | null;
  summary: Record<string, unknown> | null;
  detection: Record<string, number | string | boolean> | null;
  materiality: { band: string; score: number; exposure_rs: number; monitor_only: boolean } | null;
  hypotheses: Hypothesis[];
  options: DecisionOption[];
  certainty_state: string | null; final_confidence: number | null; lead_margin: number | null;
  certainty_reasons: string[];
  abstention: Record<string, string | number | null> | null;
  clarification: Record<string, string | boolean | string[] | null> | null;
  stage_events: { from_state: string; to_state: string; stage_code: string; ok: boolean; message: string }[];
  telemetry: { stages: number; llm_stages: number; numbers_computed_without_llm_pct: number; latency_ms_total: number };
}

export interface SecondOrderEffect {
  kpi: string; node_kind: "KPI" | "DERIVED_IMPACT"; unit: string | null;
  effect_pct: number; effect_display: string; bounds_pct: [number, number];
  confidence: number; dependency_path: string[]; hops: number;
}

export interface Collision {
  id: string; option_codes: string[]; affected_kpi: string; combined_effect_pct: number;
  severity: "HIGH" | "MEDIUM" | "LOW"; collision_type: string; owners: string[];
  combined_note: string | null; resolution_options: string[]; resolved: boolean;
  resolution?: string | null; resolution_note?: string | null;
}

export interface DecisionOption {
  id: string; code: string; driver: string; lever: string; action: string;
  expected_impact_rs: number; impact_lo_rs: number; impact_hi_rs: number;
  cost_rs: number; cash_exposure_rs: number; horizon_days: number; owner_role: string;
  simulation: { projected?: Record<string, number | null>; arithmetic?: string[];
    direct_pct?: Record<string, number>;
    second_order?: { method: string; rule: string; widening: string; effects: SecondOrderEffect[] } } | null;
  external_proposal?: boolean;
  guardrail_status: string | null; guardrail_reasons: string[];
  rights_verdict: string | null; rights_note: string | null; escalation_target: string | null;
  comparable_to: string | null; decision_health: string | null;
  record: { status: string; approved_by_role: string | null; decided_at: string | null;
            override_reason: string | null; monitoring_plan: Record<string, unknown> | null;
            actual_impact_rs: number | null; outcome_variance: number | null; within_band: boolean | null;
            outcome_note: string | null } | null;
}

export interface MemoryHit {
  id: string; title: string; period_label: string; kpi_code: string; action_taken: string;
  outcome_rs: number; within_band: boolean; lesson: string; similarity: number;
  explanation: string;
}

export interface Proposal {
  id: string; change_type: string; rationale: string; origin: string; status: string;
  base_version: number; merged_to_version: number | null; review_note: string | null;
  proposed_by_role: string | null; payload: Record<string, unknown>;
}

export interface Brief {
  persona: string; conclusion_hash: string; render_method: string; template_version: string;
  certainty_state: string | null; final_confidence: number | null;
  sections: Record<string, string>; allowed_actions: string[];
  evidence_tally: { supporting: number; contradicting: number; stale: number; withheld: number };
  withheld_sources: { doc_key: string; classification: string }[];
  postcheck_forced_template?: boolean;
}

export interface EvidenceLink {
  doc_key: string; title: string; state: string; weight: number; source: string | null;
  data_classification: string | null; freshness: number | null; lineage: string | null;
  summary: string | null; access_roles: string[];
}

export interface Hypothesis {
  id: string; code: string; statement: string; pattern_class: string; rank: number; status: string;
  support_mass: number; contradiction_mass: number; balance: number; freshness_avg: number;
  source_agreement: number; pattern_prior: number; confidence: number; final_confidence: number;
  evidence_counts: Record<string, number>; reasoning_path: string[]; evidence: EvidenceLink[];
}

export interface DecompComponent { component: string; value: number; pct: number; method: string; query_ref: string; detail: string | null; }

export interface Investigation {
  id: string; workflow_state: string; contract_version: number; period_key: string;
  reliability: number | null; confidence_cap: number | null; working_value: number | null;
  cold_start_mode: boolean; last_error: string | null;
  kpi: { code: string; name: string; unit: string } | null;
  summary: Record<string, unknown> | null;
  detection: Record<string, number | string | boolean> | null;
  materiality: { band: string; score: number; exposure_rs: number; monitor_only: boolean } | null;
  hypotheses: Hypothesis[];
  options: DecisionOption[];
  certainty_state: string | null; final_confidence: number | null; lead_margin: number | null;
  certainty_reasons: string[];
  abstention: Record<string, string | number | null> | null;
  clarification: Record<string, string | boolean | string[] | null> | null;
  stage_events: { from_state: string; to_state: string; stage_code: string; ok: boolean; message: string }[];
  telemetry: { stages: number; llm_stages: number; numbers_computed_without_llm_pct: number; latency_ms_total: number };
}

export interface SecondOrderEffect {
  kpi: string; node_kind: "KPI" | "DERIVED_IMPACT"; unit: string | null;
  effect_pct: number; effect_display: string; bounds_pct: [number, number];
  confidence: number; dependency_path: string[]; hops: number;
}

export interface Collision {
  id: string; option_codes: string[]; affected_kpi: string; combined_effect_pct: number;
  severity: "HIGH" | "MEDIUM" | "LOW"; collision_type: string; owners: string[];
  combined_note: string | null; resolution_options: string[]; resolved: boolean;
  resolution?: string | null; resolution_note?: string | null;
}

export interface DecisionOption {
  id: string; code: string; driver: string; lever: string; action: string;
  expected_impact_rs: number; impact_lo_rs: number; impact_hi_rs: number;
  cost_rs: number; cash_exposure_rs: number; horizon_days: number; owner_role: string;
  simulation: { projected?: Record<string, number | null>; arithmetic?: string[];
    direct_pct?: Record<string, number>;
    second_order?: { method: string; rule: string; widening: string; effects: SecondOrderEffect[] } } | null;
  external_proposal?: boolean;
  guardrail_status: string | null; guardrail_reasons: string[];
  rights_verdict: string | null; rights_note: string | null; escalation_target: string | null;
  comparable_to: string | null; decision_health: string | null;
  record: { status: string; approved_by_role: string | null; decided_at: string | null;
            override_reason: string | null; monitoring_plan: Record<string, unknown> | null;
            actual_impact_rs: number | null; outcome_variance: number | null; within_band: boolean | null;
            outcome_note: string | null } | null;
}

export interface MemoryHit {
  id: string; title: string; period_label: string; kpi_code: string; action_taken: string;
  outcome_rs: number; within_band: boolean; lesson: string; similarity: number;
  explanation: string;
}

export interface Proposal {
  id: string; change_type: string; rationale: string; origin: string; status: string;
  base_version: number; merged_to_version: number | null; review_note: string | null;
  proposed_by_role: string | null; payload: Record<string, unknown>;
}