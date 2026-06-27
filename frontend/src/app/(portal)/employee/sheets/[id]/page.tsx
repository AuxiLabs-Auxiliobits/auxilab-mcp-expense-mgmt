"use client";

import { useParams } from "next/navigation";
import { useSheet } from "@/data/hooks";
import { PageContainer } from "@/components/layout/page-container";
import { PageTitle } from "@/components/page-title";
import { SheetWorkspace } from "@/features/employee/sheet-workspace";

export default function SheetDetailPage() {
  const params = useParams<{ id: string }>();
  const { data: sheet } = useSheet(params.id); // deduped with the workspace's own query

  return (
    <PageContainer className="max-w-6xl">
      {/* Contextual title, e.g. "Business Trip Expense — Auxilab EM" */}
      <PageTitle title={sheet?.title || "Expense Details"} />
      <SheetWorkspace sheetId={params.id} />
    </PageContainer>
  );
}
