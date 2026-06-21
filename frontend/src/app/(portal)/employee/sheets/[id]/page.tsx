"use client";

import { useParams } from "next/navigation";
import { PageContainer } from "@/components/layout/page-container";
import { SheetWorkspace } from "@/features/employee/sheet-workspace";

export default function SheetDetailPage() {
  const params = useParams<{ id: string }>();

  return (
    <PageContainer className="max-w-6xl">
      <SheetWorkspace sheetId={params.id} />
    </PageContainer>
  );
}
