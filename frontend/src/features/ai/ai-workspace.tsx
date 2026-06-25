"use client";

/**
 * AI Workspace — the agentic dashboard. Shows advisory AI recommendations (risk, policy,
 * duplicates, missing info) for the sheets the signed-in user can act on, with full
 * explainability and accept/dismiss/feedback. Everything here is advisory: the user still acts
 * through the normal review screens. Data comes from the role-scoped `/ai/*` endpoints.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/utils";
import {
  type AiFeedbackInput,
  type AiRecommendation,
  getAiAnalytics,
  getAiWorkspace,
  postAiFeedback,
} from "@/data/ai";

const RISK_STYLES: Record<string, string> = {
  high: "bg-error/15 text-error",
  medium: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  low: "bg-primary/10 text-primary",
};

const ACTION_LABELS: Record<string, string> = {
  approve: "Looks compliant",
  review: "Worth a review",
  review_duplicate: "Check for duplicate",
  request_changes: "Return for fixes",
  add_items: "Add line items",
};

function Stat({ label, value, tone }: { label: string; value: React.ReactNode; tone?: string }) {
  return (
    <div className="rounded-xl border border-outline-variant bg-surface-container-low px-4 py-3">
      <p className={cn("text-2xl font-semibold", tone)}>{value}</p>
      <p className="text-xs text-on-surface-variant">{label}</p>
    </div>
  );
}

function RecommendationCard({ rec }: { rec: AiRecommendation }) {
  const [open, setOpen] = useState(false);
  const qc = useQueryClient();
  const fb = useMutation({
    mutationFn: (body: AiFeedbackInput) => postAiFeedback(rec.id, body),
    onSuccess: (_d, body) => {
      toast.success(
        body.decision === "accepted" ? "Marked as accepted" :
        body.decision === "dismissed" ? "Dismissed" : "Thanks for the feedback",
      );
      qc.invalidateQueries({ queryKey: ["ai-analytics"] });
    },
    onError: () => toast.error("Couldn't record feedback"),
  });

  return (
    <div className="rounded-xl border border-outline-variant bg-surface-container-lowest p-4">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="truncate font-medium text-on-surface">{rec.title ?? "Expense sheet"}</span>
            <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", RISK_STYLES[rec.risk_band])}>
              {rec.risk_band} risk · {Math.round(rec.risk_score)}
            </span>
            {!rec.policy_compliant && (
              <span className="rounded-full bg-error/15 px-2 py-0.5 text-xs text-error">policy</span>
            )}
            {rec.duplicate_band !== "none" && rec.duplicate_band !== "low" && (
              <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-xs text-amber-600 dark:text-amber-400">
                possible duplicate
              </span>
            )}
          </div>
          <p className="mt-1 text-sm text-on-surface-variant">{rec.summary}</p>
        </div>
        <span className="shrink-0 rounded-lg bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary">
          {ACTION_LABELS[rec.recommended_action] ?? rec.recommended_action}
        </span>
      </div>

      {rec.missing_info.length > 0 && (
        <ul className="mt-2 space-y-0.5 text-xs text-on-surface-variant">
          {rec.missing_info.map((m) => (
            <li key={m} className="flex items-center gap-1">
              <Icon name="info" className="text-[14px]" /> {m}
            </li>
          ))}
        </ul>
      )}

      {/* Explainability (why / data / policies) */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="mt-2 flex items-center gap-1 text-xs text-primary hover:underline"
      >
        <Icon name={open ? "expand_less" : "expand_more"} className="text-[16px]" />
        Why this recommendation
      </button>
      {open && (
        <div className="mt-2 space-y-1.5 rounded-lg bg-surface-container-low p-3 text-xs text-on-surface-variant">
          <p><strong className="text-on-surface">Why:</strong> {rec.rationale.why}</p>
          <p><strong className="text-on-surface">Data analyzed:</strong> {rec.rationale.data_analyzed.join(" · ")}</p>
          <p><strong className="text-on-surface">Policies considered:</strong> {rec.rationale.policies_considered.join(", ")}</p>
          <p><strong className="text-on-surface">Confidence:</strong> {rec.confidence}</p>
          <p className="italic">Advisory only — you make the final decision.</p>
        </div>
      )}

      <div className="mt-3 flex items-center gap-2">
        <button
          onClick={() => fb.mutate({ decision: "accepted", helpful: true })}
          disabled={fb.isPending}
          className="rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-on-primary disabled:opacity-50"
        >
          Accept suggestion
        </button>
        <button
          onClick={() => fb.mutate({ decision: "dismissed" })}
          disabled={fb.isPending}
          className="rounded-lg border border-outline-variant px-3 py-1.5 text-xs text-on-surface-variant hover:bg-surface-container"
        >
          Dismiss
        </button>
        <span className="flex-1" />
        <button onClick={() => fb.mutate({ helpful: true })} aria-label="Helpful"
          className="rounded p-1 text-on-surface-variant hover:bg-surface-container">
          <Icon name="thumb_up" className="text-[16px]" />
        </button>
        <button onClick={() => fb.mutate({ helpful: false })} aria-label="Not helpful"
          className="rounded p-1 text-on-surface-variant hover:bg-surface-container">
          <Icon name="thumb_down" className="text-[16px]" />
        </button>
      </div>
    </div>
  );
}

export function AiWorkspace() {
  const ws = useQuery({ queryKey: ["ai-workspace"], queryFn: getAiWorkspace });
  const an = useQuery({ queryKey: ["ai-analytics"], queryFn: getAiAnalytics });

  if (ws.isLoading) {
    return <div className="p-8 text-on-surface-variant">Analyzing your sheets…</div>;
  }
  if (ws.isError || !ws.data) {
    return <div className="p-8 text-error">Couldn't load the AI Workspace.</div>;
  }
  const { counts, pending_recommendations } = ws.data;

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <header className="flex items-center gap-2">
        <Icon name="auto_awesome" className="text-[26px] text-primary" />
        <div>
          <h1 className="text-xl font-semibold text-on-surface">AI Workspace</h1>
          <p className="text-sm text-on-surface-variant">
            Advisory recommendations from your digital coworker — you keep the final call.
          </p>
        </div>
      </header>

      {/* Counts + analytics */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <Stat label="Sheets analyzed" value={counts.sheets_analyzed} />
        <Stat label="High risk" value={counts.high_risk} tone={counts.high_risk ? "text-error" : undefined} />
        <Stat label="Policy issues" value={counts.policy_violations} />
        <Stat label="Duplicate candidates" value={counts.duplicate_candidates} />
        <Stat label="Missing receipts" value={counts.missing_receipts} />
      </div>
      {an.data && (
        <div className="flex flex-wrap gap-4 rounded-xl border border-outline-variant bg-surface-container-low px-4 py-3 text-sm text-on-surface-variant">
          <span>Recommendations: <strong className="text-on-surface">{an.data.recommendations_generated}</strong></span>
          <span>Acceptance: <strong className="text-on-surface">{an.data.acceptance_rate_pct ?? "—"}{an.data.acceptance_rate_pct != null ? "%" : ""}</strong></span>
          <span>Helpful: <strong className="text-on-surface">{an.data.helpful_rate_pct ?? "—"}{an.data.helpful_rate_pct != null ? "%" : ""}</strong></span>
          <span>Policy violations detected: <strong className="text-on-surface">{an.data.policy_violations_detected}</strong></span>
          <span>Duplicates flagged: <strong className="text-on-surface">{an.data.duplicate_candidates_flagged}</strong></span>
          {an.data.avg_approval_hours != null && (
            <span>Avg approval: <strong className="text-on-surface">{an.data.avg_approval_hours}h</strong></span>
          )}
        </div>
      )}

      {/* Pending recommendations */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-on-surface-variant">
          Recommendations needing attention
        </h2>
        {pending_recommendations.length === 0 ? (
          <div className="rounded-xl border border-outline-variant bg-surface-container-lowest p-8 text-center text-on-surface-variant">
            <Icon name="check_circle" className="text-[28px] text-primary" />
            <p className="mt-2">Nothing needs attention — everything looks clean. 🎉</p>
          </div>
        ) : (
          pending_recommendations.map((r) => <RecommendationCard key={r.id} rec={r} />)
        )}
      </section>
    </div>
  );
}
