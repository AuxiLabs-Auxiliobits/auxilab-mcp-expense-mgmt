"use client";

import { useAuditLog } from "@/data/hooks";
import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/shared/page-header";
import { Reveal } from "@/components/shared/reveal";
import { AuditLog } from "@/components/shared/audit-log";
import { Card } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { AgencyManagement } from "./agency-management";
import { UserManagement } from "./user-management";

/**
 * Admin console — platform administration only: onboard & manage users
 * (employee / manager / finance / admin) and agencies, with a live audit trail.
 * No policy or operational reporting here (those belong to Finance/Manager).
 */
export function AdminSettings() {
  const { data: audit, isLoading } = useAuditLog();

  return (
    <PageContainer>
      <PageHeader
        title="Administration"
        description="Onboard and manage users and agencies across the platform."
        tone="primary"
        size="xl"
      />

      <Reveal delay={80} className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <UserManagement />
          <AgencyManagement />
        </div>

        <div className="space-y-6">
          <Card className="flex flex-col overflow-hidden" style={{ height: 520 }}>
            <div className="border-b border-outline-variant bg-surface-container-lowest p-4">
              <h3 className="flex items-center gap-2 text-body-lg font-bold text-primary">
                <Icon name="security" className="text-signal-red" /> Immutable Audit Log
              </h3>
            </div>
            <div className="scrollbar-thin flex-1 overflow-y-auto">
              {isLoading ? (
                <div className="space-y-2 p-3">
                  {[0, 1, 2, 3].map((i) => (
                    <Skeleton key={i} className="h-14" />
                  ))}
                </div>
              ) : (
                <AuditLog entries={audit ?? []} />
              )}
            </div>
          </Card>
        </div>
      </Reveal>
    </PageContainer>
  );
}
