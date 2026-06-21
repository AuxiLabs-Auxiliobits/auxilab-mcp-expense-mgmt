"use client";

import { useState } from "react";
import { useCurrentUser } from "@/data/hooks";
import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/shared/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/utils";
import { ROLE_LABELS } from "@/data/types";

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-1">
      <div className="font-mono text-label-md uppercase tracking-wide text-on-surface-variant">
        {label}
      </div>
      <div className="text-body-md text-on-surface">{value}</div>
    </div>
  );
}

const PREFS = [
  { label: "Sheet status changes", desc: "Notify me when a sheet is approved, rejected, or routed.", on: true },
  { label: "Info requests", desc: "Notify me when a manager requests more information.", on: true },
  { label: "Payment confirmations", desc: "Notify me when a reimbursement is paid.", on: false },
];

export default function EmployeeSettingsPage() {
  const { data: user } = useCurrentUser("employee");
  const [prefs, setPrefs] = useState(PREFS);

  return (
    <PageContainer className="max-w-3xl">
      <PageHeader title="Settings" description="Your profile and notification preferences." tone="primary" />

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Profile</CardTitle>
          <span className="font-mono text-label-md text-on-surface-variant">
            Managed via Entra External ID
          </span>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          <Field label="Name" value={user?.name ?? "—"} />
          <Field label="Email" value={user?.email ?? "—"} />
          <Field label="Role" value={user ? ROLE_LABELS[user.role] : "—"} />
          <Field label="Agency" value={user?.agencyId ?? "—"} />
        </CardContent>
      </Card>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>Notifications</CardTitle>
        </CardHeader>
        <div className="divide-y divide-outline-variant">
          {prefs.map((p, i) => (
            <div
              key={p.label}
              className="flex items-center justify-between gap-4 px-5 py-4 transition-colors hover:bg-surface-container-low"
            >
              <div>
                <div className="text-body-sm font-medium text-on-surface">{p.label}</div>
                <div className="text-body-sm text-on-surface-variant">{p.desc}</div>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={p.on}
                aria-label={p.label}
                onClick={() =>
                  setPrefs((prev) => prev.map((x, j) => (j === i ? { ...x, on: !x.on } : x)))
                }
                className={cn(
                  "relative h-6 w-11 shrink-0 rounded-full transition-colors duration-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-secondary focus-visible:ring-offset-2 focus-visible:ring-offset-background",
                  p.on ? "bg-success-green" : "bg-surface-container-highest",
                )}
              >
                <span
                  className={cn(
                    "absolute top-0.5 h-5 w-5 rounded-full bg-surface-container-lowest shadow transition-transform duration-300 ease-spring",
                    p.on ? "translate-x-[1.375rem]" : "translate-x-0.5",
                  )}
                />
              </button>
            </div>
          ))}
        </div>
      </Card>

      <p className="mt-4 flex items-center gap-1 text-body-sm text-on-surface-variant">
        <Icon name="lock" className="text-[16px]" />
        Profile fields are read-only — identity is brokered by Microsoft Entra External ID.
      </p>
    </PageContainer>
  );
}
