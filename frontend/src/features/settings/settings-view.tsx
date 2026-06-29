"use client";

import { useCurrentUser, usePreferences, useUpdatePreferences } from "@/data/hooks";
import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/shared/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { ROLE_LABELS, type Role } from "@/data/types";

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

function Toggle({
  on,
  label,
  disabled,
  onClick,
}: {
  on: boolean;
  label: string;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "relative h-6 w-11 shrink-0 rounded-full transition-colors duration-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-secondary focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:opacity-50",
        on ? "bg-success-green" : "bg-surface-container-highest",
      )}
    >
      <span
        className={cn(
          "absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform duration-300 ease-spring",
          on ? "translate-x-[1.25rem]" : "translate-x-0",
        )}
      />
    </button>
  );
}

/** Stable preference keys persisted via PUT /me/preferences. Defaults MUST match the
 *  backend's notification-category defaults (api notification_service._PREF_DEFAULTS). */
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

/**
 * Shared Settings surface for every role (employee/manager/finance). Profile is read-only
 * (sourced from /auth/me); notifications + appearance persist the user's own choices.
 */
export function SettingsView({ role }: { role: Role }) {
  const { data: user } = useCurrentUser(role);
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
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          <Field label="Name" value={user?.name ?? "—"} />
          <Field label="Email" value={user?.email ?? "—"} />
          <Field label="Role" value={user ? ROLE_LABELS[user.role] : "—"} />
          <Field label="Agency" value={user?.agencyName ?? user?.agencyId ?? "—"} />
          <p className="col-span-full text-label-sm text-on-surface-variant">
            Profile details come from your account — contact your administrator to change them.
          </p>
        </CardContent>
      </Card>

      <Card className="mt-4">
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Notifications</CardTitle>
          {update.isPending ? (
            <span className="font-mono text-label-md text-on-surface-variant">Saving…</span>
          ) : update.isError ? (
            <span className="font-mono text-label-md text-error">Couldn&apos;t save — try again</span>
          ) : update.isSuccess ? (
            <span className="flex items-center gap-1 font-mono text-label-md text-success-green">
              <Icon name="check" className="text-[14px]" /> Saved
            </span>
          ) : null}
        </CardHeader>
        {isLoading ? (
          <div className="divide-y divide-outline-variant">
            {PREFS.map((p) => (
              <div key={p.key} className="flex items-center justify-between gap-4 px-5 py-4">
                <div className="space-y-2">
                  <Skeleton className="h-4 w-40" />
                  <Skeleton className="h-3 w-64" />
                </div>
                <Skeleton className="h-6 w-11 rounded-full" />
              </div>
            ))}
          </div>
        ) : (
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
                  <Toggle on={on} label={p.label} onClick={() => toggle(p.key)} />
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </PageContainer>
  );
}
