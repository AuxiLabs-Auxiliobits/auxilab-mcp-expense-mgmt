import { cn } from "@/lib/utils";

const TONES = {
  success: "bg-success-green",
  primary: "bg-primary",
  tertiary: "bg-tertiary",
  error: "bg-error",
} as const;

/** Pulsing "live"/active status dot with an expanding ring (pauses under reduced-motion). */
export function LiveDot({
  tone = "success",
  className,
}: {
  tone?: keyof typeof TONES;
  className?: string;
}) {
  const color = TONES[tone];
  return (
    <span className={cn("relative inline-flex h-2.5 w-2.5", className)}>
      <span
        className={cn(
          "absolute inline-flex h-full w-full animate-ping rounded-full opacity-60",
          color,
        )}
      />
      <span className={cn("relative inline-flex h-2.5 w-2.5 rounded-full", color)} />
    </span>
  );
}
