import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/utils";

export function EmptyState({
  icon = "inbox",
  title,
  description,
  className,
  children,
}: {
  icon?: string;
  title: string;
  description?: string;
  className?: string;
  children?: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "flex animate-fade-in flex-col items-center justify-center gap-2 px-6 py-12 text-center",
        className,
      )}
    >
      <div className="flex h-14 w-14 animate-scale-in items-center justify-center rounded-full bg-gradient-to-br from-surface-container-high to-surface-container text-on-surface-variant shadow-xs ring-1 ring-outline-variant/50">
        <Icon name={icon} className="text-[26px]" />
      </div>
      <h3 className="text-body-lg font-semibold text-on-surface">{title}</h3>
      {description && (
        <p className="max-w-sm text-body-sm text-on-surface-variant">{description}</p>
      )}
      {children}
    </div>
  );
}
