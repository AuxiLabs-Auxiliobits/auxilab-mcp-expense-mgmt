"use client";

import Link from "next/link";
import { useEmployeeKpis } from "@/data/hooks";
import { KpiTile } from "@/components/shared/kpi-tile";
import { Reveal } from "@/components/shared/reveal";
import { Counter } from "@/components/shared/counter";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { formatCurrency } from "@/lib/format";

const usd = (n: number) => formatCurrency(n);

export function EmployeeKpiRow({ employeeId }: { employeeId: string }) {
  const { data, isLoading } = useEmployeeKpis(employeeId);

  if (isLoading || !data) {
    return (
      <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-32 rounded-lg" />
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
      <Reveal delay={0} className="h-full">
        <KpiTile
          className="h-full"
          label="Reimbursed This Month"
          value={<Counter value={data.reimbursedThisMonth} format={usd} />}
          icon="trending_up"
          iconClassName="text-success-green"
          footer={
            <p className="font-mono text-label-md text-on-surface-variant">
              Paid &amp; approved this period
            </p>
          }
        />
      </Reveal>

      <Reveal delay={80} className="h-full">
        <KpiTile
          className="h-full"
          label="Pending Approval"
          value={<Counter value={data.pendingApprovalValue} format={usd} />}
          unit={`/ ${data.pendingApprovalCount} Sheets`}
          icon="hourglass_empty"
          iconClassName="text-yellow-500"
          footer={
            <p className="flex items-center gap-1 font-mono text-label-md text-on-surface-variant">
              <Icon name="info" className="text-[14px]" />
              Expected processing in 3 days
            </p>
          }
        />
      </Reveal>

      <Reveal delay={160} className="h-full">
        <KpiTile
          className="h-full"
          label="Drafts Value"
          value={<Counter value={data.draftsValue} format={usd} />}
          icon="draft"
          footer={
            <Link
              href="/employee/sheets"
              className="flex items-center gap-1 font-mono text-label-md text-secondary hover:underline"
            >
              Complete drafts <Icon name="arrow_forward" className="text-[14px]" />
            </Link>
          }
        />
      </Reveal>
    </div>
  );
}
