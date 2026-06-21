import { cn } from "@/lib/utils";

/**
 * Passthrough wrapper. (Cursor-follow "magnetic" motion was removed — it's a
 * consumer/marketing flourish with no place in enterprise software.)
 */
export function Magnetic({
  children,
  className,
}: {
  children: React.ReactNode;
  strength?: number;
  max?: number;
  className?: string;
}) {
  return <span className={cn("inline-block", className)}>{children}</span>;
}
