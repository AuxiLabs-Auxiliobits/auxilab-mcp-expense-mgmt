"use client";

import Link from "next/link";
import { useAuditLog } from "@/data/hooks";
import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/shared/page-header";
import { Reveal } from "@/components/shared/reveal";
import { AuditLog } from "@/components/shared/audit-log";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { AgencyManagement } from "./agency-management";
import { BaselinePolicyViewer } from "./baseline-policy-viewer";
import { RoleAssignmentForm } from "./role-assignment-form";

export function AdminSettings() {
  const { data: audit, isLoading } = useAuditLog();

  return (
    <PageContainer>
      <PageHeader
        title="Platform Settings"
        description="Manage agencies, global policies, and platform audit logs."
        tone="primary"
        size="xl"
      >
        <Button variant="outline">Export Logs</Button>
        <Button>Save Changes</Button>
      </PageHeader>

      <Reveal delay={80} className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <AgencyManagement />
          <BaselinePolicyViewer />
        </div>

        <div className="space-y-6">
          <RoleAssignmentForm />

          <Card className="flex flex-col overflow-hidden" style={{ height: 400 }}>
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
            <div className="border-t border-outline-variant bg-surface-container-low p-2 text-center">
              <Link href="#" className="text-body-sm text-primary hover:underline">
                View Full Log Repository
              </Link>
            </div>
          </Card>
        </div>
      </Reveal>
    </PageContainer>
  );
}
