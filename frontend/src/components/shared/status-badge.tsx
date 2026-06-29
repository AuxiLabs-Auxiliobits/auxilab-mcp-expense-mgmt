import { Badge } from "@/components/ui/badge";
import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/utils";
import type { StatusMeta } from "@/lib/status";

export function StatusBadge({
  meta,
  showIcon = true,
  className,
}: {
  meta: StatusMeta;
  showIcon?: boolean;
  className?: string;
}) {
  return (
    // Uniform across all statuses — same height/padding/radius/size/weight;
    // only color + icon differ (rounded-md forced over any caller override).
    <Badge pill={false} className={cn(meta.badgeClass, className, "rounded-md")}>
      {showIcon && <Icon name={meta.icon} className="text-[14px]" />}
      {meta.label}
    </Badge>
  );
}
