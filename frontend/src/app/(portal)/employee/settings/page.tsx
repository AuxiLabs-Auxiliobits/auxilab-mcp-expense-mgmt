"use client";

import { useCurrentUser, usePreferences, useUpdatePreferences } from "@/data/hooks";
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

/** Stable preference keys persisted via PUT /me/preferences. */
const PREFS = [
  {
    key: "statusChanges",
    label: "Sheet status changes",
    desc: "Notify me when a sheet is approved, rejected, or routed.",
    fallback: true,
  },
  {
    key: "infoRequests",
    label: "Info requests",
    desc: "Notify me when a manager requests more information.",
    fallback: true,
  },
  {
    key: "paymentConfirmations",
    label: "Payment confirmations",
    desc: "Notify me when a reimbursement is paid.",
    fallback: false,
  },
] as const;

export default function EmployeeSettingsPage() {
  const { data: user } = useCurrentUser("employee");
  const { data: prefs, isLoading } = usePreferences();
  const update = useUpdatePreferences();

  const isOn = (p: (typeof PREFS)[number]) =>
    prefs && p.key in prefs ? Boolean(prefs[p.key]) : p.fallback;

  // Persist the full set so every key is stored, flipping just the toggled one.
  const toggle = (key: string) => {
    const next = Object.fromEntries(
      PREFS.map((p) => [p.key, p.key === key ? !isOn(p) : isOn(p)]),
    );
    update.mutate(next);
  };

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
          <Field label="Agency" value={user?.agencyName ?? user?.agencyId ?? "—"} />
        </CardContent>
      </Card>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>Notifications</CardTitle>
          {update.isError && (
            <span className="font-mono text-label-md text-error">Couldn&apos;t save — try again</span>
          )}
        </CardHeader>
        <div className="divide-y divide-outline-variant">
          {PREFS.map((p) => {
            const on = isOn(p);
            return (
              <div
                key={p.key}
                className="flex items-center justify-between gap-4 px-5 py-4 transition-colors hover:bg-surface-container-low"
              >
                <div>
                  <div className="text-body-sm font-medium text-on-surface">{p.label}</div>
                  <div className="text-body-sm text-on-surface-variant">{p.desc}</div>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={on}
                  aria-label={p.label}
                  disabled={isLoading}
                  onClick={() => toggle(p.key)}
                  className={cn(
                    "relative h-6 w-11 shrink-0 rounded-full transition-colors duration-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-secondary focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:opacity-50",
                    on ? "bg-success-green" : "bg-surface-container-highest",
                  )}
                >
                  <span
                    className={cn(
                      "absolute top-0.5 h-5 w-5 rounded-full bg-surface-container-lowest shadow transition-transform duration-300 ease-spring",
                      on ? "translate-x-[1.375rem]" : "translate-x-0.5",
                    )}
                  />
                </button>
              </div>
            );
          })}
        </div>
      </Card>

    </PageContainer>
  );
}
