"use client";

import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/shared/page-header";
import { Icon } from "@/components/ui/icon";
import { ActivityTable } from "@/features/shared/activity-table";

export default function ManagerAuditPage() {
  return (
    <PageContainer>
      <PageHeader
        title="Agency Activity"
        description="The audit trail for your agency — your team's submissions, your reviews, and finance decisions."
      />

      <div className="mt-4 flex items-center gap-2 rounded-lg border border-outline-variant bg-surface-container-low px-4 py-3 text-body-sm text-on-surface-variant">
        <Icon name="info" className="text-[18px] text-secondary" />
        You see activity for everyone in your agency. The full org-wide trail is restricted to
        Finance and Admin.
      </div>

      <ActivityTable />
    </PageContainer>
  );
}
