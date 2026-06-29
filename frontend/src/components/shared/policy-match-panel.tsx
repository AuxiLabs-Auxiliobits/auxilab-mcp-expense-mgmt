"use client";

import { useSheetPolicyCheck } from "@/data/hooks";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

/**
 * Live "does this sheet match the policy?" panel. Calls the read-only RAG policy-check
 * endpoint and shows: the AI verdict + confidence, the cited policy clauses (which points
 * matched / were violated), and the exact policy chunks retrieved from the agency's indexed
 * document. Works on ANY sheet (manual-review or already auto-approved) so Finance can audit
 * how the expense lines up with the policy.
 */
export function PolicyMatchPanel({ sheetId }: { sheetId: string }) {
  const { data, isLoading, isError } = useSheetPolicyCheck(sheetId);

  if (isLoading) {
    return (
      <div className="space-y-2">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-12 rounded" />
        ))}
      </div>
    );
  }

  if (isError || !data) {
    return (
      <p className="text-body-sm text-on-surface-variant">
        Couldn&apos;t evaluate this sheet against the policy right now.
      </p>
    );
  }

  const approved = data.decision === "APPROVED";
  const pct = Math.round(data.confidence * 100);

  return (
    <div className="space-y-4">
      {/* Verdict banner */}
      <div
        className={cn(
          "flex items-start gap-3 rounded-lg border p-3",
          approved
            ? "border-success-green/20 bg-success-green/5"
            : "border-error/20 bg-error-container",
        )}
      >
        <Icon
          name={approved ? "verified" : "gpp_maybe"}
          className={cn("mt-0.5 text-[20px]", approved ? "text-success-green" : "text-error")}
        />
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-2 text-body-md font-semibold text-on-surface">
            {approved ? "Matches policy — would auto-approve" : "Does not cleanly match — route to human"}
            <span className="font-mono text-label-sm font-medium text-on-surface-variant">
              {pct}% confidence
            </span>
          </p>
          <p className="mt-0.5 text-label-sm text-on-surface-variant">
            {data.llmUsed
              ? "Evaluated by the AI approver against the agency's indexed policy."
              : data.policyFound
                ? "Policy retrieved; AI model unavailable — receipt-scan checks applied."
                : "No agency policy is indexed yet — receipt-scan checks only. Upload & publish a policy to enable full matching."}
          </p>
          {data.reasonDetail && (
            <p className="mt-1 text-body-sm text-on-surface">{data.reasonDetail}</p>
          )}
        </div>
      </div>

      {/* Cited clauses — the specific policy points that matched / were violated */}
      {data.citedClauses.length > 0 && (
        <div>
          <p className="mb-1.5 font-mono text-label-md font-bold uppercase text-on-surface-variant">
            {approved ? "Policy points satisfied" : "Policy concerns"}
          </p>
          <ul className="space-y-1">
            {data.citedClauses.map((c, i) => (
              <li key={i} className="flex items-start gap-2 text-body-sm text-on-surface">
                <Icon
                  name={approved ? "check_circle" : "error"}
                  className={cn(
                    "mt-0.5 shrink-0 text-[14px]",
                    approved ? "text-success-green" : "text-error",
                  )}
                />
                {c}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Retrieved policy evidence — the exact indexed policy text the sheet was checked against */}
      {data.evidence.length > 0 && (
        <details className="group rounded-lg border border-outline-variant bg-surface-container-lowest">
          <summary className="flex cursor-pointer items-center gap-2 px-3 py-2 text-body-sm font-medium text-on-surface">
            <Icon
              name="chevron_right"
              className="text-[18px] text-on-surface-variant transition-transform group-open:rotate-90"
            />
            <Icon name="menu_book" className="text-[16px] text-secondary" />
            Policy excerpts checked ({data.evidence.length})
          </summary>
          <div className="space-y-2 px-3 pb-3">
            {data.evidence.map((e, i) => (
              <div
                key={i}
                className="rounded border border-outline-variant bg-surface-container-low p-2.5"
              >
                <p className="mb-1 font-mono text-label-sm text-on-surface-variant">
                  Policy {e.policyVersion}
                </p>
                <p className="whitespace-pre-wrap text-body-sm text-on-surface-variant">{e.text}</p>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
