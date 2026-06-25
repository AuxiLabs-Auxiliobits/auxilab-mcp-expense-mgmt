/**
 * Client for the agentic platform (`/ai/*`). All advisory — these endpoints read recommendations
 * the user is already allowed to see and record feedback; none of them mutate a sheet.
 */
import { apiGet, apiPost } from "./http";

export interface AiRationale {
  why: string;
  data_analyzed: string[];
  policies_considered: string[];
  total_at_risk?: string;
}

export interface AiRecommendation {
  id: string;
  sheet_id: string;
  title?: string;
  summary: string;
  risk_score: number;
  risk_band: "low" | "medium" | "high";
  policy_compliant: boolean;
  duplicate_likelihood: number;
  duplicate_band: "none" | "low" | "medium" | "high";
  missing_info: string[];
  recommended_action: string;
  confidence: "low" | "medium" | "high";
  rationale: AiRationale;
  sheet_status?: string;
  created_at?: string;
}

export interface AiWorkspace {
  role: string;
  counts: {
    sheets_analyzed: number;
    high_risk: number;
    policy_violations: number;
    duplicate_candidates: number;
    missing_receipts: number;
  };
  pending_recommendations: AiRecommendation[];
  high_risk: AiRecommendation[];
  duplicate_candidates: AiRecommendation[];
  policy_violations: AiRecommendation[];
  missing_receipts: AiRecommendation[];
  recent_ai_actions: {
    sheet_id: string;
    action: string;
    risk_band: string;
    recommended_action: string;
    at: string | null;
  }[];
}

export interface AiAnalytics {
  recommendations_generated: number;
  current_recommendations: number;
  by_risk_band: { low: number; medium: number; high: number };
  policy_violations_detected: number;
  duplicate_candidates_flagged: number;
  feedback_count: number;
  acceptance_rate_pct: number | null;
  helpful_rate_pct: number | null;
  avg_approval_hours: number | null;
  engagement_pct: number | null;
}

export interface AiFeedbackInput {
  helpful?: boolean;
  decision?: "accepted" | "ignored" | "dismissed";
  reason?: string;
}

export const getAiWorkspace = () => apiGet<AiWorkspace>("/ai/workspace");
export const getAiAnalytics = () => apiGet<AiAnalytics>("/ai/analytics");
export const postAiFeedback = (recId: string, body: AiFeedbackInput) =>
  apiPost<{ ok: boolean }>(`/ai/recommendations/${recId}/feedback`, body);
