import { Card } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/utils";

/** Operational KPI tile: label + metric + optional delta and footer slot.
 *  Static by design — no hover motion or cursor effects (enterprise standard). */
export function KpiTile({
  label,
  value,
  unit,
  icon,
  iconClassName,
  delta,
  footer,
  children,
  className,
}: {
  label: string;
  value: React.ReactNode;
  unit?: React.ReactNode;
  icon?: string;
  iconClassName?: string;
  delta?: { value: string; direction: "up" | "down"; tone?: "success" | "error" };
  footer?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <Card className={cn("flex flex-col justify-between p-5", className)}>
      <div>
        <div className="mb-2 flex items-center justify-between">
          <span className="font-mono text-label-md font-semibold uppercase tracking-wider text-on-surface-variant">
            {label}
          </span>
          {icon && (
            <Icon name={icon} className={cn("text-[20px] text-on-surface-variant", iconClassName)} />
          )}
        </div>
        <div className="flex items-end gap-2">
          <span className="text-headline-lg font-semibold tabular-nums text-on-surface">{value}</span>
          {unit && <span className="font-mono text-label-md text-on-surface-variant">{unit}</span>}
          {delta && (
            <span
              className={cn(
                "mb-1 flex items-center font-mono text-label-md uppercase",
                delta.tone === "error" ? "text-error" : "text-success-green",
              )}
            >
              <Icon
                name={delta.direction === "up" ? "arrow_upward" : "arrow_downward"}
                className="text-[16px]"
              />
              {delta.value}
            </span>
          )}
        </div>
      </div>
      {(children || footer) && <div className="mt-4">{children ?? footer}</div>}
    </Card>
  );
}
