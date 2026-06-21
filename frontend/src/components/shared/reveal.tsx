import { cn } from "@/lib/utils";

/**
 * Layout passthrough. (Scroll-triggered fade/stagger was removed — enterprise
 * tools render data immediately; reveal-on-scroll is a marketing pattern.)
 * Kept as a thin wrapper so existing call sites keep their layout classes.
 */
export function Reveal({
  children,
  className,
}: {
  children: React.ReactNode;
  delay?: number;
  className?: string;
}) {
  return <div className={cn(className)}>{children}</div>;
}
