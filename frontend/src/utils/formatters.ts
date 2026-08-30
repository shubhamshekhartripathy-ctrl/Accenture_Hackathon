/**
 * Format raw backend KPI identifiers into business-readable titles.
 */
export function formatIdentifier(code: string): string {
  const map: Record<string, string> = {
    revenue_ne: "Revenue (Northeast)",
    osa_ne: "On-Shelf Availability (Northeast)",
    inventory_cover_ne: "Inventory Cover (Northeast)",
    stockout_risk_ne: "Stockout Risk (Northeast)",
    complaints_rate_ne: "Complaints Rate (Northeast)",
    marketing_roi: "Marketing ROI",
    supplier_reliability: "Supplier Reliability",
    customer_sla: "Customer SLA",
  };
  return map[code] || code.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase());
}

/**
 * Format raw certainty states into semantic descriptions.
 */
export function formatCertainty(state: string): string {
  switch (state) {
    case "ACT_WITH_CAUTION": return "Proceed with caution";
    case "CLARIFY": return "Needs clarification";
    case "ABSTAIN": return "Insufficient data to act";
    default: return state;
  }
}

/**
 * Format rights check verdicts into business-readable labels.
 */
export function formatRightsVerdict(verdict: string): string {
  switch (verdict) {
    case "ESCALATE": return "Requires Executive Escalation";
    case "BLOCKED": return "Action Blocked by Policy";
    case "AUTHORIZED": return "Pre-Approved Action";
    default: return verdict;
  }
}

/**
 * Get the explanation for a rights check verdict.
 */
export function getRightsExplanation(verdict: string): string {
  switch (verdict) {
    case "ESCALATE": return "You lack authorization to approve this directly.";
    case "BLOCKED": return "Option exceeds all authorization limits and cannot be approved.";
    case "AUTHORIZED": return "Option is within your authorization limits.";
    default: return "";
  }
}
