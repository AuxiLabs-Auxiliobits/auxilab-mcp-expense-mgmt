"use client";

// REFERENCE SCAFFOLD ONLY — see README.md.
// AG Grid Enterprise master-detail stub: sheet rows (master) → line items (detail),
// per SCOPING §10 (grouping, master-detail, server-side rows, Excel export).
// This is a typed STUB — the real grid would import ag-grid-react + ag-grid-enterprise,
// register the LicenseManager, and wire server-side row + master-detail configs.

import type { ColDef } from "ag-grid-community";
import type { ExpenseSheet, LineItem } from "@/types";

// import { AgGridReact } from "ag-grid-react";
// import { LicenseManager } from "ag-grid-enterprise";
// import "ag-grid-community/styles/ag-grid.css";
// import "ag-grid-community/styles/ag-theme-quartz.css";
// LicenseManager.setLicenseKey(process.env.NEXT_PUBLIC_AG_GRID_LICENSE!);

interface SheetGridProps {
  // "queue" = many sheets (employee/manager/finance lists); "single-sheet" = one sheet's items.
  mode?: "queue" | "single-sheet";
  sheetId?: string;
}

// Master columns (sheet level).
const sheetColumns: ColDef<ExpenseSheet>[] = [
  { field: "id", headerName: "Sheet" },
  { field: "version" },
  { field: "status" },
  { field: "period" },
  { field: "financeDecision", headerName: "Finance Decision" },
];

// Detail columns (line-item level) — used by AG Grid masterDetail.detailGridOptions.
const lineItemColumns: ColDef<LineItem>[] = [
  { field: "category" },
  { field: "amount" },
  { field: "currency" },
  { field: "merchant" },
  { field: "managerStatus", headerName: "Manager" },
  { field: "policyStatus", headerName: "LLM Policy" },
  { field: "policyClauseRef", headerName: "Cited Clause" },
];

export function SheetGrid({ mode = "queue", sheetId }: SheetGridProps) {
  // TODO(reference): real implementation —
  //   const { data } = useQuery({ queryKey: queryKeys.sheets, queryFn: ... });
  //   return (
  //     <div className="ag-theme-quartz" style={{ height: 600 }}>
  //       <AgGridReact<ExpenseSheet>
  //         rowData={data}
  //         columnDefs={sheetColumns}
  //         masterDetail
  //         detailCellRendererParams={{
  //           detailGridOptions: { columnDefs: lineItemColumns },
  //           getDetailRowData: (p) => p.successCallback(p.data.lineItems),
  //         }}
  //         rowModelType="serverSide"
  //       />
  //     </div>
  //   );

  // Reference the column defs so they are exercised by the type-checker.
  void sheetColumns;
  void lineItemColumns;

  return (
    <div className="rounded-md border border-dashed p-8 text-sm text-muted-foreground">
      STUB: AG Grid Enterprise master-detail ({mode}
      {sheetId ? ` · ${sheetId}` : ""}). Master = sheets, detail = line items with
      manager + LLM verdicts. Server-side row model + Excel export wired in the real
      component.
    </div>
  );
}
