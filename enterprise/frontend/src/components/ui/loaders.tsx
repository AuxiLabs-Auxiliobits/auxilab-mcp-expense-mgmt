/**
 * Reusable loading primitives so every screen signals in-flight work consistently.
 * Queries use the skeletons; mutations use the Button `loading` prop or <Spinner/>.
 */
import { cn } from "@/lib/utils";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";

/** Inline spinning indicator (Material "progress_activity"). */
export function Spinner({ className }: { className?: string }) {
  return (
    <Icon
      name="progress_activity"
      aria-hidden
      className={cn("animate-spin text-[18px] text-on-surface-variant", className)}
    />
  );
}

/** Centered spinner + label for a whole region/section that's still loading. */
export function SectionLoader({ label = "Loading…", className }: { label?: string; className?: string }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn("flex flex-col items-center justify-center gap-2 py-12 text-on-surface-variant", className)}
    >
      <Spinner className="text-[24px] text-secondary" />
      <span className="text-body-sm">{label}</span>
    </div>
  );
}

/** Full-viewport loader for route-level transitions. */
export function FullPageLoader({ label = "Loading…" }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="grid min-h-[60vh] place-items-center">
      <div className="flex flex-col items-center gap-3 text-on-surface-variant">
        <Spinner className="text-[28px] text-secondary" />
        <span className="text-body-sm">{label}</span>
      </div>
    </div>
  );
}

/** Skeleton rows for a data table while it loads. */
export function TableSkeleton({ rows = 6, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div role="status" aria-live="polite" aria-label="Loading table" className="space-y-2">
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex gap-3">
          {Array.from({ length: cols }).map((_, c) => (
            <Skeleton key={c} className={cn("h-9 flex-1", c === 0 && "max-w-[40%]")} />
          ))}
        </div>
      ))}
    </div>
  );
}

/** Skeleton block for a card/widget while it loads. */
export function CardSkeleton({ className }: { className?: string }) {
  return (
    <div role="status" aria-live="polite" aria-label="Loading" className={cn("space-y-3 rounded-lg border border-outline-variant p-4", className)}>
      <Skeleton className="h-4 w-1/3" />
      <Skeleton className="h-8 w-2/3" />
      <Skeleton className="h-3 w-1/2" />
    </div>
  );
}

/** A determinate progress bar (0–100) for uploads/downloads. */
export function ProgressBar({ value, className }: { value: number; className?: string }) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div
      role="progressbar"
      aria-valuenow={pct}
      aria-valuemin={0}
      aria-valuemax={100}
      className={cn("h-1.5 w-full overflow-hidden rounded-full bg-surface-container-high", className)}
    >
      <div className="h-full rounded-full bg-secondary transition-[width] duration-200" style={{ width: `${pct}%` }} />
    </div>
  );
}
