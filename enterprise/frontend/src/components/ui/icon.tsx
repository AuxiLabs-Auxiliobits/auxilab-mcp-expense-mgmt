import { cn } from "@/lib/utils";

/** Thin wrapper over the Material Symbols Outlined icon font. */
export function Icon({
  name,
  className,
  filled,
}: {
  name: string;
  className?: string;
  filled?: boolean;
}) {
  return (
    <span
      aria-hidden
      className={cn("material-symbols-outlined", filled && "fill", className)}
    >
      {name}
    </span>
  );
}
