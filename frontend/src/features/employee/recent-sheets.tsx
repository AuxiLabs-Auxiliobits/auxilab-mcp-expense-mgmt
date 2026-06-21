"use client";

import Link from "next/link";
import { useEmployeeSheets } from "@/data/hooks";
import { StatusBadge } from "@/components/shared/status-badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { SHEET_STATUS_META } from "@/lib/status";
import { formatCurrency } from "@/lib/format";
import { cn } from "@/lib/utils";

export function RecentSheets({ employeeId }: { employeeId: string }) {
  const { data, isLoading } = useEmployeeSheets(employeeId);
  const sheets = (data ?? []).filter((s) => s.status !== "DRAFT").slice(0, 5);

  return (
    <Card className="flex h-full flex-col shadow-sm">
      <CardHeader>
        <CardTitle>Recent Sheets</CardTitle>
        <Link
          href="/employee/sheets"
          className="font-mono text-label-md text-secondary hover:underline"
        >
          View All
        </Link>
      </CardHeader>
      <div className="flex flex-col gap-0.5 p-2">
        {isLoading
          ? [0, 1, 2].map((i) => <Skeleton key={i} className="h-16 rounded" />)
          : sheets.map((sheet) => (
              <Link
                key={sheet.id}
                href={`/employee/sheets/${sheet.id}`}
                className={cn(
                  "group cursor-pointer rounded-md border border-transparent p-3 transition-colors duration-150 hover:border-outline-variant hover:bg-surface-container-low",
                  sheet.status === "PAID" && "opacity-70",
                )}
              >
                <div className="mb-1 flex items-start justify-between gap-3">
                  <h4 className="text-body-sm font-medium text-on-surface">{sheet.title}</h4>
                  <span className="font-mono text-label-md font-medium text-on-surface">
                    {formatCurrency(sheet.total, sheet.currency)}
                  </span>
                </div>
                <div className="mt-2 flex items-center justify-between">
                  <span className="font-mono text-label-md text-on-surface-variant">{sheet.id}</span>
                  <StatusBadge meta={SHEET_STATUS_META[sheet.status]} className="rounded" />
                </div>
              </Link>
            ))}
      </div>
    </Card>
  );
}
