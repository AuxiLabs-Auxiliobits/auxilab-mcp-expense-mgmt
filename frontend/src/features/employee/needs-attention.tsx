"use client";

import Link from "next/link";
import { useEmployeeSheets } from "@/data/hooks";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { SheetStatus } from "@/data/types";

interface AttentionItem {
  icon: string;
  tone: string;
  title: string;
  desc: string;
  cta: string;
  href: string;
}

const EDITABLE: SheetStatus[] = ["DRAFT", "RETURNED_TO_EMPLOYEE"];

/** Operational "what needs my action" widget with direct actions. */
export function NeedsAttention({ employeeId }: { employeeId: string }) {
  const { data: sheets, isLoading } = useEmployeeSheets(employeeId);
  const list = sheets ?? [];

  const returned = list.filter((s) => s.status === "RETURNED_TO_EMPLOYEE");
  const drafts = list.filter((s) => s.status === "DRAFT");
  const missing = list
    .filter((s) => EDITABLE.includes(s.status))
    .reduce((n, s) => n + s.lineItems.filter((li) => li.attachments.length === 0).length, 0);

  const items: AttentionItem[] = [];
  if (returned.length)
    items.push({
      icon: "undo",
      tone: "text-error",
      title: `${returned.length} sheet${returned.length > 1 ? "s" : ""} returned to you`,
      desc: "Address the manager feedback and resubmit.",
      cta: "Review",
      href: `/employee/sheets/${returned[0].id}`,
    });
  if (missing)
    items.push({
      icon: "receipt_long",
      tone: "text-yellow-600",
      title: `${missing} line item${missing > 1 ? "s" : ""} missing a receipt`,
      desc: "Attach receipts before these sheets can be submitted.",
      cta: "Fix",
      href: "/employee/receipts",
    });
  if (drafts.length)
    items.push({
      icon: "draft",
      tone: "text-secondary",
      title: `${drafts.length} draft${drafts.length > 1 ? "s" : ""} to complete`,
      desc: "Finish adding items and submit for approval.",
      cta: "Complete",
      href: `/employee/sheets/${drafts[0].id}`,
    });

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>Needs your attention</CardTitle>
        {items.length > 0 && (
          <span className="rounded-full bg-error-container px-2 py-0.5 font-mono text-label-sm font-semibold text-error">
            {items.length}
          </span>
        )}
      </CardHeader>
      {isLoading ? (
        <div className="space-y-2 p-4">
          {[0, 1].map((i) => (
            <Skeleton key={i} className="h-12" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="flex items-center gap-3 px-5 py-6">
          <Icon name="task_alt" className="text-[26px] text-success-green" />
          <div>
            <p className="text-body-sm font-medium text-on-surface">You&apos;re all caught up</p>
            <p className="text-body-sm text-on-surface-variant">
              No returns, drafts, or missing receipts.
            </p>
          </div>
        </div>
      ) : (
        <ul className="divide-y divide-outline-variant">
          {items.map((it) => (
            <li key={it.title} className="flex items-center gap-3 px-5 py-3">
              <span
                className={cn(
                  "flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-surface-container-high",
                  it.tone,
                )}
              >
                <Icon name={it.icon} className="text-[18px]" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-body-sm font-medium text-on-surface">{it.title}</p>
                <p className="text-label-md text-on-surface-variant">{it.desc}</p>
              </div>
              <Button variant="outline" size="sm" asChild>
                <Link href={it.href}>{it.cta}</Link>
              </Button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
