import { cn } from "@/lib/utils";

const SIZES = {
  xs: "h-3 w-3 border-2",
  sm: "h-4 w-4 border-2",
  md: "h-6 w-6 border-2",
  lg: "h-9 w-9 border-[3px]",
} as const;

/**
 * A small, on-brand loading spinner — a spinning ring drawn from the current text
 * colour, so it inherits context (`text-secondary` by default, `text-current` inside
 * buttons). Use for any indeterminate wait; pair with `<PageSpinner>` for full-area waits.
 */
export function Spinner({
  size = "md",
  className,
}: {
  size?: keyof typeof SIZES;
  className?: string;
}) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={cn(
        "inline-block shrink-0 animate-spin rounded-full border-current border-t-transparent text-secondary",
        SIZES[size],
        className,
      )}
    />
  );
}

/** Centered spinner that fills its container — for route/page and full-section waits. */
export function PageSpinner({
  label,
  className,
}: {
  label?: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex min-h-[40vh] w-full flex-col items-center justify-center gap-3",
        className,
      )}
    >
      <Spinner size="lg" />
      {label && <p className="text-body-sm text-on-surface-variant">{label}</p>}
    </div>
  );
}
