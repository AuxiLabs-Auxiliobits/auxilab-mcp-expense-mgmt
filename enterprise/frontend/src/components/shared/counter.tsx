"use client";

/**
 * Renders a number using the supplied formatter. (Animated count-up was removed
 * — enterprise dashboards display data instantly; no marketing-style motion.)
 */
export function Counter({
  value,
  format = (n) => String(Math.round(n)),
}: {
  value: number;
  format?: (n: number) => string;
  durationMs?: number;
}) {
  return <>{format(value)}</>;
}
