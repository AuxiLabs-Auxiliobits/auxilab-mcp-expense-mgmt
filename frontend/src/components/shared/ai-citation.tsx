import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/utils";

/**
 * Citation-first component (DESIGN.md): AI-generated text is always anchored to
 * a visible policy clause tag. Inline variant used in the line-item grids.
 */
export function AiCitation({
  message,
  clauseRef,
  severity = "warning",
  className,
}: {
  message: string;
  clauseRef: string;
  severity?: "warning" | "error";
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-[11px]",
        severity === "error"
          ? "border-error/30 bg-error-container/50 text-on-error-container"
          : "border-yellow-500/30 bg-surface text-yellow-600",
        className,
      )}
    >
      <Icon name="smart_toy" className="text-[12px]" />
      <span className="font-sans">{message}</span>
      <span className="ml-1 cursor-pointer border-l border-outline-variant pl-1 text-outline hover:text-primary">
        {clauseRef}
      </span>
    </span>
  );
}

/** Block citation used in the Finance review detail (blockquote + clause name). */
export function CitedClause({
  policyName,
  text,
  className,
}: {
  policyName: string;
  text: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "rounded border border-outline-variant bg-surface-container-low p-4",
        className,
      )}
    >
      <p className="mb-2 font-mono text-label-md font-bold uppercase text-on-surface-variant">
        Cited Policy Clause ({policyName})
      </p>
      <blockquote className="border-l-4 border-primary pl-3 text-body-sm italic text-on-surface">
        “{text}”
      </blockquote>
    </div>
  );
}
