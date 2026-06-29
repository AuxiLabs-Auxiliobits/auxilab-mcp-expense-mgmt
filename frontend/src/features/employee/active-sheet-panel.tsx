"use client";

import { useState } from "react";
import Link from "next/link";
import { useActiveDraft } from "@/data/hooks";
import { AiCitation } from "@/components/shared/ai-citation";
import { ReceiptPreview } from "@/components/shared/receipt-preview";
import { EmptyState } from "@/components/shared/empty-state";
import { Card } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { CATEGORY_ICON } from "@/lib/status";
import { formatCurrency, formatShortDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { LineItem } from "@/data/types";

const GRID = "grid grid-cols-[auto_1fr_auto_auto_auto] gap-4 px-5";

export function ActiveSheetPanel({ employeeId }: { employeeId: string }) {
  const { data: sheet, isLoading } = useActiveDraft(employeeId);

  if (isLoading) {
    return (
      <Card className="flex h-full flex-col shadow-sm">
        <Skeleton className="h-14 rounded-t-lg" />
        <div className="space-y-3 p-5">
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
        </div>
      </Card>
    );
  }

  if (!sheet) {
    return (
      <Card className="flex h-full flex-col justify-center shadow-sm">
        <EmptyState
          icon="note_add"
          title="No active draft"
          description="Start a new expense sheet to add line items and attachments."
        >
          <Link
            href="/employee/sheets/new"
            className="mt-2 inline-flex items-center gap-2 rounded bg-primary px-4 py-2 text-body-sm font-medium text-on-primary hover:bg-on-primary-fixed-variant"
          >
            <Icon name="add" className="text-[18px]" /> New Sheet
          </Link>
        </EmptyState>
      </Card>
    );
  }

  return (
    <Card className="flex h-full flex-col shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between rounded-t-lg border-b border-outline-variant bg-surface-bright px-5 py-4">
        <div className="flex items-center gap-3">
          <h3 className="text-body-lg font-semibold text-on-surface">{sheet.title}</h3>
          <span className="flex items-center gap-1 rounded-full bg-secondary-fixed px-2 py-0.5 text-[11px] font-semibold text-on-secondary-fixed-variant">
            <span className="h-1.5 w-1.5 rounded-full bg-secondary" />
            Draft
          </span>
        </div>
        <span className="font-mono text-label-md text-on-surface-variant">{sheet.period}</span>
      </div>

      {/* Grid */}
      <div className="flex-1 overflow-x-auto">
        <div
          className={cn(
            GRID,
            "min-w-[600px] border-b border-outline-variant bg-surface-container-low py-2.5 text-[13px] font-semibold text-on-surface-variant",
          )}
        >
          <div className="w-8" />
          <div>Merchant / Category</div>
          <div className="w-24 text-right">Date</div>
          <div className="w-20 text-center">Receipt</div>
          <div className="w-24 text-right">Amount</div>
        </div>

        <div className="flex min-w-[600px] flex-col">
          {sheet.lineItems.map((item) => (
            <LineItemRow key={item.id} item={item} />
          ))}
        </div>
      </div>

      {/* Footer */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-b-lg border-t border-outline-variant px-5 py-4">
        <Link
          href={`/employee/sheets/${sheet.id}`}
          className="flex items-center gap-1 text-body-sm text-on-surface-variant transition-colors hover:text-primary"
        >
          <Icon name="add_circle" className="text-[18px]" /> Add Line Item
        </Link>
        <div className="flex items-center gap-4">
          <div className="font-mono text-label-md text-on-surface-variant">
            Total:{" "}
            <span className="text-body-lg font-bold text-on-surface">
              {formatCurrency(sheet.total, sheet.currency)}
            </span>
          </div>
          <Link
            href={`/employee/sheets/${sheet.id}`}
            className="rounded bg-primary px-4 py-1.5 text-body-sm font-medium text-on-primary transition-opacity hover:opacity-90"
          >
            Review &amp; Submit
          </Link>
        </div>
      </div>
    </Card>
  );
}

function LineItemRow({ item }: { item: LineItem }) {
  const flagged = !!item.aiFlag;
  const receipt = item.attachments[0];
  const hasReceipt = !!receipt;
  const [previewOpen, setPreviewOpen] = useState(false);

  return (
    <div
      className={cn(
        GRID,
        "group relative cursor-pointer border-b border-outline-variant py-3 transition-colors",
        flagged ? "bg-error-container/20 hover:bg-error-container/30" : "hover:bg-surface-container-low",
      )}
    >
      {flagged && (
        <span
          className={cn(
            "absolute left-0 top-0 h-full w-1",
            item.aiFlag?.severity === "error" ? "bg-error" : "bg-yellow-500",
          )}
        />
      )}
      <div className="flex w-8 items-center">
        <input
          type="checkbox"
          className="h-4 w-4 rounded border-outline-variant text-secondary focus:ring-secondary"
        />
      </div>
      <div>
        <div className="text-body-sm font-medium text-on-surface">{item.merchant}</div>
        <div className="mt-0.5 flex items-center gap-1 font-mono text-label-md text-on-surface-variant">
          <Icon name={CATEGORY_ICON[item.category] ?? "category"} className="text-[14px]" />
          {item.category}
        </div>
        {item.aiFlag && (
          <div className="mt-1">
            <AiCitation
              message={item.aiFlag.message}
              clauseRef={item.aiFlag.clauseRef}
              severity={item.aiFlag.severity}
            />
          </div>
        )}
      </div>
      <div className="flex w-24 items-center justify-end font-mono text-label-md text-on-surface-variant">
        {formatShortDate(item.expenseDate)}
      </div>
      <div className="flex w-20 items-center justify-center">
        {hasReceipt ? (
          <>
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  onClick={() => setPreviewOpen(true)}
                  aria-label={`Preview receipt ${receipt.fileName}`}
                  className="rounded p-1 text-secondary transition-colors hover:bg-secondary-fixed"
                >
                  <Icon name="attachment" className="text-[18px]" />
                </button>
              </TooltipTrigger>
              <TooltipContent>View attachment</TooltipContent>
            </Tooltip>
            <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
              <DialogContent className="max-w-3xl">
                <DialogHeader>
                  <DialogTitle className="truncate">{receipt.fileName}</DialogTitle>
                </DialogHeader>
                <div className="flex h-[70vh] items-center justify-center overflow-hidden rounded-lg border border-outline-variant bg-surface-container-low">
                  <ReceiptPreview
                    variant="full"
                    downloadUrl={receipt.downloadUrl}
                    fileName={receipt.fileName}
                    fileType={receipt.fileType}
                  />
                </div>
              </DialogContent>
            </Dialog>
          </>
        ) : (
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="rounded p-1 text-error" aria-label="Missing receipt">
                <Icon name="receipt_long" className="text-[18px]" />
              </span>
            </TooltipTrigger>
            <TooltipContent>Missing receipt</TooltipContent>
          </Tooltip>
        )}
      </div>
      <div className="flex w-24 items-center justify-end font-mono text-label-md font-medium text-on-surface">
        {formatCurrency(item.amount, item.currency)}
      </div>
    </div>
  );
}
