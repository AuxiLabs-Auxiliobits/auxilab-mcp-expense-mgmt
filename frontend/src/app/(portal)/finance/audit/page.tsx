"use client";

import { useActivityLog, useCurrentUser } from "@/data/hooks";
import { useSessionRole } from "@/components/session-role";
import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/shared/page-header";
import { AuditLog } from "@/components/shared/audit-log";
import { EmptyState } from "@/components/shared/empty-state";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";

export default function FinanceAuditPage() {
  const { sessionRole } = useSessionRole();
  const isAdmin = sessionRole === "admin";
  const role = isAdmin ? "admin" : "finance";
  const { data: user } = useCurrentUser(role);
  const { data, isLoading } = useActivityLog(role, user?.id ?? "");
  const entries = data ?? [];

  return (
    <PageContainer>
      <PageHeader
        title={isAdmin ? "Platform Audit Log" : "My Activity"}
        description={
          isAdmin
            ? "Complete, replayable record of every action across employees, managers, finance, and the AI approver."
            : "Your finance decisions and policy actions — your own audit trail."
        }
      >
        <Button variant="outline">
          <Icon name="download" /> Export
        </Button>
      </PageHeader>

      <div className="mt-4 flex items-center gap-2 rounded-lg border border-outline-variant bg-surface-container-low px-4 py-3 text-body-sm text-on-surface-variant">
        <Icon name={isAdmin ? "shield_person" : "info"} className="text-[18px] text-secondary" />
        {isAdmin
          ? "Admin view — you see the entire platform's activity, every role included."
          : "You see only your own actions. The org-wide log is restricted to Admin."}
      </div>

      <Card className="mt-6 overflow-hidden">
        {isLoading ? (
          <div className="space-y-2 p-4">
            {[0, 1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-14" />
            ))}
          </div>
        ) : entries.length === 0 ? (
          <EmptyState
            icon="history"
            title="No activity yet"
            description="Decisions and policy actions will appear here."
          />
        ) : (
          <AuditLog entries={entries} />
        )}
      </Card>
    </PageContainer>
  );
}
