"use client";

import { useCurrentUser, useMyAuditLog } from "@/data/hooks";
import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/shared/page-header";
import { AuditLog } from "@/components/shared/audit-log";
import { EmptyState } from "@/components/shared/empty-state";
import { Card } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";

export default function ManagerAuditPage() {
  const { data: user } = useCurrentUser("manager");
  const { data, isLoading } = useMyAuditLog(user?.id ?? "");
  const entries = data ?? [];

  return (
    <PageContainer>
      <PageHeader
        title="My Activity"
        description="Your recorded approvals, rejections, and info requests — your own audit trail."
      />

      <div className="mt-4 flex items-center gap-2 rounded-lg border border-outline-variant bg-surface-container-low px-4 py-3 text-body-sm text-on-surface-variant">
        <Icon name="info" className="text-[18px] text-secondary" />
        You see only your own actions. The org-wide immutable audit log is restricted to
        Finance and Admin.
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
            description="Your approvals and rejections will appear here as you review sheets."
          />
        ) : (
          <AuditLog entries={entries} />
        )}
      </Card>
    </PageContainer>
  );
}
