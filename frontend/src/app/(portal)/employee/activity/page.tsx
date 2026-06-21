"use client";

import { useActivityLog, useCurrentUser } from "@/data/hooks";
import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/shared/page-header";
import { AuditLog } from "@/components/shared/audit-log";
import { EmptyState } from "@/components/shared/empty-state";
import { Card } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";

export default function EmployeeActivityPage() {
  const { data: user } = useCurrentUser("employee");
  const { data, isLoading } = useActivityLog("employee", user?.id ?? "");
  const entries = data ?? [];

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

      <Card className="mt-6 overflow-hidden">
        {isLoading ? (
          <div className="space-y-2 p-4">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-14" />
            ))}
          </div>
        ) : entries.length === 0 ? (
          <EmptyState
            icon="history"
            title="No activity yet"
            description="Submit an expense sheet and it'll show up here."
          />
        ) : (
          <AuditLog entries={entries} />
        )}
      </Card>
    </PageContainer>
  );
}
