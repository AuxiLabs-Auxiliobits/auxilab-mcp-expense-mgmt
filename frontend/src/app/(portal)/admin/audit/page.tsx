"use client";

import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/shared/page-header";
import { Icon } from "@/components/ui/icon";
import { ActivityTable } from "@/features/shared/activity-table";

export default function AdminAuditPage() {
  return (
    <PageContainer>
      <PageHeader
        title="Platform Audit Log"
        description="Complete, replayable record of every action across employees, managers, finance, and the AI approver."
      />

      <div className="mt-4 flex items-center gap-2 rounded-lg border border-outline-variant bg-surface-container-low px-4 py-3 text-body-sm text-on-surface-variant">
        <Icon name="shield_person" className="text-[18px] text-secondary" />
        Org-wide view — Finance and Admin see the entire platform&apos;s activity, every role included.
      </div>

      <ActivityTable />
    </PageContainer>
  );
}
