"use client";

import { useEffect, useState } from "react";
import { useActivity } from "@/data/hooks";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { AuditLogEntry } from "@/data/types";

const SEVERITY_TEXT: Record<AuditLogEntry["severity"], string> = {
  info: "text-tertiary",
  success: "text-success-green",
  warning: "text-yellow-600",
  error: "text-error",
};

const PAGE_SIZE = 15;

/**
 * Role-scoped audit/activity table with search + pagination. The backend (`GET /activity`)
 * decides what the caller may see (employee→own, manager→agency, finance/admin→org-wide),
 * so this component is identical across roles.
 */
export function ActivityTable({ actorId }: { actorId?: string }) {
  const [q, setQ] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    const t = setTimeout(() => {
      setDebouncedQ(q.trim());
      setPage(1);
    }, 350);
    return () => clearTimeout(t);
  }, [q]);

  const { data, isLoading, isFetching } = useActivity({
    page,
    pageSize: PAGE_SIZE,
    q: debouncedQ || undefined,
    actor_id: actorId,
  });
  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="mt-6 space-y-3">
      {/* Filter bar */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative w-full sm:max-w-sm">
          <Icon
            name="search"
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[18px] text-on-surface-variant"
          />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search action or entity…"
            className="pl-9"
            aria-label="Search activity"
          />
        </div>
        <p className="font-mono text-label-md text-on-surface-variant">
          {total} event{total === 1 ? "" : "s"}
          {isFetching && !isLoading ? " · updating…" : ""}
        </p>
      </div>

      <Card className="overflow-hidden">
        {isLoading ? (
          <div className="space-y-2 p-4">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-12" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <EmptyState
            icon="history"
            title={debouncedQ ? "No matching activity" : "No activity yet"}
            description={
              debouncedQ
                ? "Try a different search term."
                : "Actions you (and those you oversee) take will appear here."
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-body-sm">
              <thead className="border-b border-outline-variant bg-surface-container-low font-mono text-label-sm uppercase tracking-wider text-on-surface-variant">
                <tr>
                  <th className="px-4 py-2.5 font-medium">When</th>
                  <th className="px-4 py-2.5 font-medium">Who</th>
                  <th className="px-4 py-2.5 font-medium">Action</th>
                  <th className="px-4 py-2.5 font-medium">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant">
                {items.map((e) => (
                  <tr key={e.id} className="align-top transition-colors hover:bg-surface-bright">
                    <td
                      className="whitespace-nowrap px-4 py-2.5 font-mono text-label-sm text-on-surface-variant"
                      title={new Date(e.timestamp).toLocaleString()}
                    >
                      {formatRelative(e.timestamp)}
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="font-medium text-on-surface">{e.actorName || "System"}</div>
                      {e.actorRole && (
                        <div className="font-mono text-label-sm uppercase tracking-wide text-on-surface-variant">
                          {e.actorRole}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className={cn("font-mono text-label-sm font-bold", SEVERITY_TEXT[e.severity])}>
                        {e.action}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-on-surface">
                      {e.summary}
                      {e.entity && (
                        <span className="ml-1 font-mono text-label-sm text-on-surface-variant">· {e.entity}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex items-center justify-between">
          <span className="font-mono text-label-md text-on-surface-variant">
            Page {page} of {pages}
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1 || isFetching}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              <Icon name="chevron_left" /> Prev
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= pages || isFetching}
              onClick={() => setPage((p) => Math.min(pages, p + 1))}
            >
              Next <Icon name="chevron_right" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
