import Link from "next/link";
import { Icon } from "@/components/ui/icon";
import { formatDateTimeIST, formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { AuditLogEntry } from "@/data/types";

const TONE: Record<AuditLogEntry["severity"], { wrap: string; icon: string }> = {
  success: { wrap: "bg-success-green/10 text-success-green", icon: "check_circle" },
  warning: { wrap: "bg-yellow-500/10 text-yellow-600", icon: "warning" },
  error: { wrap: "bg-error-container text-error", icon: "cancel" },
  info: { wrap: "bg-secondary-container text-secondary", icon: "bolt" },
};

function deepLink(e: AuditLogEntry, sheetHref: (id: string) => string): string | null {
  if (e.entity?.startsWith("expense_sheet:")) {
    const id = e.entity.split(":")[1];
    if (id) return sheetHref(id);
  }
  if (e.reference && /^SH-/.test(e.reference)) return sheetHref(e.reference);
  return null;
}

/** Modern enterprise activity timeline: actor, action summary, timestamp, deep link. */
export function ActivityFeed({
  entries,
  limit = 6,
  sheetHref = (id) => `/employee/sheets/${id}`,
}: {
  entries: AuditLogEntry[];
  limit?: number;
  /** Builds the sheet URL from a sheet ID. Defaults to the employee route. */
  sheetHref?: (id: string) => string;
}) {
  const items = entries.slice(0, limit);
  if (items.length === 0) {
    return <p className="px-5 py-8 text-center text-body-sm text-on-surface-variant">No recent activity.</p>;
  }
  return (
    <ul className="divide-y divide-outline-variant">
      {items.map((e) => {
        const tone = TONE[e.severity];
        const href = deepLink(e, sheetHref);
        const inner = (
          <div className="flex items-start gap-3 px-5 py-3">
            <span className={cn("mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full", tone.wrap)}>
              <Icon name={tone.icon} className="text-[18px]" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-body-sm text-on-surface">{e.summary}</p>
              <p className="mt-0.5 font-mono text-label-sm text-on-surface-variant">
                {e.actorName} · <span title={formatRelative(e.timestamp)}>{formatDateTimeIST(e.timestamp)}</span>
              </p>
            </div>
            {href && (
              <Icon name="chevron_right" className="mt-1.5 shrink-0 text-[18px] text-on-surface-variant" />
            )}
          </div>
        );
        return (
          <li key={e.id} className={cn(href && "transition-colors hover:bg-surface-container-low")}>
            {href ? (
              <Link href={href} className="block">
                {inner}
              </Link>
            ) : (
              inner
            )}
          </li>
        );
      })}
    </ul>
  );
}
