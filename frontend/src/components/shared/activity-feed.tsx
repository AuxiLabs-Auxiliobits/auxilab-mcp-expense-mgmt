import Link from "next/link";
import { Icon } from "@/components/ui/icon";
import { formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { AuditLogEntry } from "@/data/types";

const TONE: Record<AuditLogEntry["severity"], { wrap: string; icon: string }> = {
  success: { wrap: "bg-success-green/10 text-success-green", icon: "check_circle" },
  warning: { wrap: "bg-yellow-500/10 text-yellow-600", icon: "warning" },
  error: { wrap: "bg-error-container text-error", icon: "cancel" },
  info: { wrap: "bg-secondary-container text-secondary", icon: "bolt" },
};

function deepLink(reference?: string): string | null {
  if (reference && /^SH-/.test(reference)) return `/employee/sheets/${reference}`;
  return null;
}

/** Modern enterprise activity timeline: actor, action summary, timestamp, deep link. */
export function ActivityFeed({ entries, limit = 6 }: { entries: AuditLogEntry[]; limit?: number }) {
  const items = entries.slice(0, limit);
  if (items.length === 0) {
    return <p className="px-5 py-8 text-center text-body-sm text-on-surface-variant">No recent activity.</p>;
  }
  return (
    <ul className="divide-y divide-outline-variant">
      {items.map((e) => {
        const tone = TONE[e.severity];
        const href = deepLink(e.reference);
        const inner = (
          <div className="flex items-start gap-3 px-5 py-3">
            <span className={cn("mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full", tone.wrap)}>
              <Icon name={tone.icon} className="text-[18px]" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-body-sm text-on-surface">{e.summary}</p>
              <p className="mt-0.5 font-mono text-label-sm text-on-surface-variant">
                {e.actorName} · {formatRelative(e.timestamp)}
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
