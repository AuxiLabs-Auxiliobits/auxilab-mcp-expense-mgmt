"use client";

import { useState } from "react";
import { scanReceipt, type ReceiptScan } from "@/data/api";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { formatCurrency } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Currency } from "@/data/types";

/** Human labels for the extraction backend that produced the scan. */
const SOURCE_META: Record<string, { label: string; tone: string }> = {
  document_intelligence: { label: "Document Intelligence", tone: "text-secondary" },
  text: { label: "Text extraction", tone: "text-on-surface-variant" },
  unavailable: { label: "Unavailable", tone: "text-on-surface-variant" },
};

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-label-sm font-medium uppercase tracking-wide text-on-surface-variant">{label}</dt>
      <dd className="font-mono text-body-sm text-on-surface">{value}</dd>
    </div>
  );
}

/**
 * Manager/Finance-only view of a receipt's scan-derived values (Document Intelligence).
 *
 * Fetched on demand from the view-scoped `/scan` endpoint and rendered as labelled fields
 * (merchant / total / tax / reconciliation). This is intentionally NOT rendered in the
 * employee flow — only the manager and finance review screens surface the extraction
 * (the employee just uploads; the scan runs server-side).
 */
export function ReceiptScanDetails({
  sheetId,
  lineItemId,
  currency = "USD",
}: {
  sheetId: string;
  lineItemId: string;
  /** Currency of the line item, used to format the scanned total/tax. */
  currency?: Currency;
}) {
  const [scan, setScan] = useState<ReceiptScan | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await scanReceipt({ sheetId, lineItemId });
      setScan(res);
      setOpen(true);
      if (!res) setError("No scanned values available for this receipt.");
    } catch {
      setError("Couldn't read the receipt scan — there may be no receipt attached.");
      setOpen(true);
    } finally {
      setLoading(false);
    }
  }

  if (!open) {
    return (
      <div className="mt-3 border-t border-outline-variant/30 pt-3">
        <Button variant="outline" size="sm" loading={loading} onClick={load}>
          <Icon name="document_scanner" /> View scanned values
        </Button>
      </div>
    );
  }

  const source = scan ? SOURCE_META[scan.source] ?? SOURCE_META.unavailable : null;
  // The scan reconciles when the extracted total matches what the employee entered.
  const reconciles = scan?.reconciles ?? scan?.matchesEntered;

  return (
    <div className="mt-3 space-y-3 border-t border-outline-variant/30 pt-3">
      <div className="flex items-center justify-between">
        <p className="flex items-center gap-1.5 font-mono text-label-md uppercase tracking-wide text-on-surface-variant">
          <Icon name="document_scanner" className="text-[14px] text-secondary" />
          Receipt scan · derived values
        </p>
        <button
          type="button"
          className="text-label-md text-on-surface-variant hover:text-on-surface"
          onClick={() => setOpen(false)}
        >
          Hide
        </button>
      </div>

      {error || !scan ? (
        <p className="text-body-sm text-on-surface-variant">
          {error ?? "No scanned values available for this receipt."}
        </p>
      ) : (
        <div className="space-y-3 rounded border border-outline-variant bg-surface-container p-3">
          {source && (
            <div className="flex items-center gap-1.5">
              <Icon name="auto_awesome" className={cn("text-[14px]", source.tone)} />
              <span className={cn("text-label-sm font-medium", source.tone)}>
                Extracted via {source.label}
              </span>
            </div>
          )}

          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3">
            {scan.merchant != null && <Field label="Merchant" value={scan.merchant} />}
            {scan.total != null && (
              <Field label="Total" value={formatCurrency(scan.total, currency)} />
            )}
            {scan.tax != null && <Field label="Tax" value={formatCurrency(scan.tax, currency)} />}
            {scan.receiptDatetime != null && (
              <Field label="Receipt date" value={scan.receiptDatetime} />
            )}
          </dl>

          {reconciles != null && (
            <div
              className={cn(
                "flex items-center gap-1.5 rounded px-2 py-1 text-label-md font-medium",
                reconciles
                  ? "bg-success-green/10 text-success-green"
                  : "bg-error-container text-error",
              )}
            >
              <Icon name={reconciles ? "check_circle" : "error"} className="text-[16px]" />
              {reconciles
                ? "Reconciles with the entered amount"
                : "Does not match the entered amount"}
              {scan.delta != null && scan.delta !== 0 && (
                <span className="font-mono">· Δ {formatCurrency(scan.delta, currency)}</span>
              )}
            </div>
          )}

          {scan.detail && <p className="text-body-sm text-on-surface-variant">{scan.detail}</p>}
        </div>
      )}
    </div>
  );
}
