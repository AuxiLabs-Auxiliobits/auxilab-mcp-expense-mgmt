import * as React from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  /** Pass status badge classes from lib/status, or override entirely. */
  pill?: boolean;
}

/** Low-saturation status pill (DESIGN.md component spec). */
export function Badge({ className, pill = true, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 text-[12px] font-medium leading-5",
        pill ? "rounded-full" : "rounded-md",
        className,
      )}
      {...props}
    />
  );
}
