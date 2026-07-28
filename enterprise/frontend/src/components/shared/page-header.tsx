import { cn } from "@/lib/utils";
import { Breadcrumb } from "./breadcrumb";

export function PageHeader({
  title,
  description,
  size = "lg",
  children,
}: {
  title: string;
  description?: string;
  /** Retained for compatibility; titles are now neutral (enterprise standard). */
  tone?: "default" | "primary";
  size?: "lg" | "xl";
  children?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
      <div>
        <Breadcrumb />
        <h1
          className={cn(
            "text-balance font-semibold text-on-surface",
            size === "xl" ? "text-headline-lg sm:text-headline-xl" : "text-headline-lg",
          )}
        >
          {title}
        </h1>
        {description && (
          <p className="mt-1 max-w-2xl text-pretty text-body-sm text-on-surface-variant">
            {description}
          </p>
        )}
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </div>
  );
}
