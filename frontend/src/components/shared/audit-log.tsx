import { Icon } from "@/components/ui/icon";
import { formatDateTimeIST, formatRelative } from "@/lib/format";
import { friendlyAction } from "@/lib/status";
import { cn } from "@/lib/utils";
import type { AuditLogEntry } from "@/data/types";

const SEVERITY_TEXT: Record<AuditLogEntry["severity"], string> = {
  info: "text-tertiary",
  success: "text-success-green",
  warning: "text-yellow-600",
  error: "text-error",
};

export function AuditLog({ entries }: { entries: AuditLogEntry[] }) {
  return (
    <ul className="divide-y divide-outline-variant">
      {entries.map((entry) => (
        <li key={entry.id} className="p-3 transition-colors hover:bg-surface-bright">
          <div className="mb-1 flex items-start justify-between">
            <span className={cn("text-label-sm font-bold", SEVERITY_TEXT[entry.severity])}>
              {friendlyAction(entry.action)}
            </span>
            <span
              className="font-mono text-[10px] text-on-surface-variant"
              title={formatRelative(entry.timestamp)}
            >
              {formatDateTimeIST(entry.timestamp)}
            </span>
          </div>
          {/* Show a human summary only when it isn't just the raw action code. */}
          {entry.summary && entry.summary !== entry.action && (
            <p className="text-body-sm text-on-surface">{entry.summary}</p>
          )}
          {(entry.reference || entry.hash) && (
            <p className="mt-1 flex items-center gap-1 font-mono text-[10px] text-on-surface-variant">
              <Icon name="tag" className="text-[12px]" />
              {entry.hash ? `Hash: ${entry.hash}` : entry.reference}
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}
