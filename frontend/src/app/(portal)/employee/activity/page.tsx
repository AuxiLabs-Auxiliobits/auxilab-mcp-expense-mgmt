"use client";

import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/shared/page-header";
import { Icon } from "@/components/ui/icon";
import { ActivityTable } from "@/features/shared/activity-table";

export default function EmployeeActivityPage() {
  return (
    <PageContainer>
      <PageHeader
        title="My Activity"
        description="Your submissions, resubmissions, and withdrawals — your own audit trail."
        tone="primary"
      />

      <div className="mt-4 flex items-center gap-2 rounded-lg border border-outline-variant bg-surface-container-low px-4 py-3 text-body-sm text-on-surface-variant">
        <Icon name="info" className="text-[18px] text-secondary" />
        You see only your own actions. Manager, Finance, and AI-approver decisions on your
        sheets show on each sheet&apos;s detail page.
      </div>

      <ActivityTable />
    </PageContainer>
  );
}
