// REFERENCE SCAFFOLD ONLY — see README.md.
// SHEET DETAIL — one expense sheet with its line items (master-detail placeholder).
// Shows sheet-level status + finance decision and, per line item, the manager
// verdict and the LLM policy verdict with the cited clause (SCOPING §5, §5.1, §6.3).

import { SheetGrid } from "@/components/SheetGrid";

interface PageProps {
  params: Promise<{ sheetId: string }>;
}

export default async function SheetDetailPage({ params }: PageProps) {
  const { sheetId } = await params;

  // TODO(reference): TanStack Query / server fetch → GET /sheets/:sheetId
  // (apiClient.sheets.get). The backend enforces that the caller may view this
  // sheet (own sheet, own-agency manager, or finance/admin) — SCOPING §3.2/§3.3.

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-xl font-semibold">Expense Sheet</h1>
        <p className="text-sm text-muted-foreground">
          Sheet ID <code>{sheetId}</code> — stable across resubmissions; version
          increments each resubmit (§5.1). Finance decision is all-or-nothing: if the
          LLM rejects any line item, the whole sheet is rejected (§5).
        </p>
      </header>

      {/* Master-detail: sheet header row → expand to line items + attachments. */}
      <SheetGrid mode="single-sheet" sheetId={sheetId} />

      <p className="text-xs text-muted-foreground">
        STUB: line items show category, amount, merchant, manager verdict, and the
        LLM policy verdict (POLICY_PASS / POLICY_FAIL / POLICY_UNCERTAIN) with the
        cited agency policy clause.
      </p>
    </section>
  );
}
