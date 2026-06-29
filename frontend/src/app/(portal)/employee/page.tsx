"use client";

import Link from "next/link";
import { useCurrentUser, useActivity } from "@/data/hooks";
import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/shared/page-header";
import { ActivityFeed } from "@/components/shared/activity-feed";
import { EmployeeKpiRow } from "@/features/employee/kpi-row";
import { NeedsAttention } from "@/features/employee/needs-attention";
import { ActiveSheetPanel } from "@/features/employee/active-sheet-panel";
import { RecentSheets } from "@/features/employee/recent-sheets";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";

export default function EmployeeDashboardPage() {
  const { data: user } = useCurrentUser("employee");
  const employeeId = user?.id ?? "";
  const firstName = user?.name?.split(" ")[0];
  const { data: activity } = useActivity({ page: 1, pageSize: 6 });

  return (
    <PageContainer>
      <PageHeader
        title={firstName ? `Welcome back, ${firstName}` : "Overview"}
        description="Here's what needs your attention and your recent activity."
      >
        <Button asChild>
          <Link href="/employee/sheets/new">
            <Icon name="add" /> New Sheet
          </Link>
        </Button>
      </PageHeader>

      <div className="mt-8">
        <EmployeeKpiRow employeeId={employeeId} />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <NeedsAttention employeeId={employeeId} />
        <Card className="flex flex-col">
          <CardHeader>
            <CardTitle>Recent activity</CardTitle>
            <Link
              href="/employee/activity"
              className="font-mono text-label-md text-secondary hover:underline"
            >
              View all
            </Link>
          </CardHeader>
          <ActivityFeed entries={activity?.items ?? []} />
        </Card>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <ActiveSheetPanel employeeId={employeeId} />
        </div>
        <div>
          <RecentSheets employeeId={employeeId} />
        </div>
      </div>
    </PageContainer>
  );
}
