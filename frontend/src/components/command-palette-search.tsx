"use client";

/**
 * Lazy, role-scoped global search for the command palette (Phase 4).
 * Only mounts while the palette is open AND a query is present, so the underlying queries
 * are fetched on first use, not on every page load. Each role renders only the hooks it is
 * permitted to call (no forbidden 403 requests) — true RBAC-aware search (Phase 11).
 */

import { Command } from "cmdk";
import {
  useAgencies,
  useAllSheets,
  useCurrentUser,
  useEmployeeSheets,
  useManagerQueue,
  useNotifications,
} from "@/data/hooks";
import { bestFuzzyScore } from "@/lib/command-fuzzy";
import { Highlight } from "@/components/command-highlight";
import { Icon } from "@/components/ui/icon";
import type { AppNotification, ExpenseSheet, Role } from "@/data/types";

const CAP = 6;

function rank<T>(items: T[], query: string, fields: (i: T) => string[]): T[] {
  return items
    .map((item) => ({ item, score: bestFuzzyScore(query, fields(item)) }))
    .filter((x) => x.score >= 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, CAP)
    .map((x) => x.item);
}

function Row({
  value,
  icon,
  query,
  title,
  subtitle,
  onRun,
}: {
  value: string;
  icon: string;
  query: string;
  title: string;
  subtitle?: string;
  onRun: () => void;
}) {
  return (
    <Command.Item
      value={value}
      onSelect={onRun}
      className="flex cursor-pointer items-center gap-3 rounded-lg px-2.5 py-2 text-body-sm text-on-surface outline-none transition-colors data-[selected=true]:bg-surface-container-high"
    >
      <Icon name={icon} className="shrink-0 text-[18px] text-on-surface-variant" />
      <span className="min-w-0 flex-1 truncate">
        <Highlight query={query} text={title} />
      </span>
      {subtitle && (
        <span className="shrink-0 truncate text-label-md text-on-surface-variant">{subtitle}</span>
      )}
    </Command.Item>
  );
}

function NotificationResults({
  role,
  query,
  onRun,
}: {
  role: Role;
  query: string;
  onRun: (href: string) => void;
}) {
  const { data, isLoading } = useNotifications(role);
  if (isLoading) return null;
  const hits = rank<AppNotification>(data ?? [], query, (n) => [n.title, n.body ?? ""]);
  if (hits.length === 0) return null;
  return (
    <Command.Group heading="Notifications">
      {hits.map((n) => (
        <Row
          key={n.id}
          value={`notif:${n.id}`}
          icon={n.icon || "notifications"}
          query={query}
          title={n.title}
          onRun={() => onRun(n.href || notificationHome(role))}
        />
      ))}
    </Command.Group>
  );
}

function notificationHome(role: Role): string {
  if (role === "employee") return "/employee/activity";
  if (role === "manager") return "/manager/audit";
  return "/finance/audit";
}

function SheetRows({
  heading,
  sheets,
  query,
  hrefFor,
  onRun,
}: {
  heading: string;
  sheets: ExpenseSheet[];
  query: string;
  hrefFor: (s: ExpenseSheet) => string;
  onRun: (href: string) => void;
}) {
  const hits = rank(sheets, query, (s) => [s.title ?? "", s.employeeName ?? ""]);
  if (hits.length === 0) return null;
  return (
    <Command.Group heading={heading}>
      {hits.map((s) => (
        <Row
          key={s.id}
          value={`sheet:${s.id}`}
          icon="description"
          query={query}
          title={s.title || "Untitled sheet"}
          subtitle={s.employeeName ?? s.status}
          onRun={() => onRun(hrefFor(s))}
        />
      ))}
    </Command.Group>
  );
}

// ── Role-specific search trees (each calls only permitted hooks) ──
function EmployeeSearch({ query, onRun }: { query: string; onRun: (href: string) => void }) {
  const { data: user } = useCurrentUser("employee");
  const { data: sheets } = useEmployeeSheets(user?.id ?? "");
  return (
    <>
      <SheetRows
        heading="My Expense Sheets"
        sheets={sheets ?? []}
        query={query}
        hrefFor={(s) => `/employee/sheets/${s.id}`}
        onRun={onRun}
      />
      <NotificationResults role="employee" query={query} onRun={onRun} />
    </>
  );
}

function ManagerSearch({ query, onRun }: { query: string; onRun: (href: string) => void }) {
  const { data: user } = useCurrentUser("manager");
  const { data: sheets } = useManagerQueue(user?.agencyId ?? "");
  return (
    <>
      <SheetRows
        heading="Pending Approvals"
        sheets={sheets ?? []}
        query={query}
        hrefFor={() => "/manager"}
        onRun={onRun}
      />
      <NotificationResults role="manager" query={query} onRun={onRun} />
    </>
  );
}

function FinanceSearch({ role, query, onRun }: { role: Role; query: string; onRun: (href: string) => void }) {
  const { data: sheets } = useAllSheets();
  const { data: agencies } = useAgencies(role === "admin");
  return (
    <>
      <SheetRows
        heading="Expense Sheets"
        sheets={sheets ?? []}
        query={query}
        hrefFor={() => "/finance/sheets"}
        onRun={onRun}
      />
      {role === "admin" && agencies && (() => {
        const hits = rank(agencies, query, (a) => [a.name ?? ""]);
        return hits.length ? (
          <Command.Group heading="Agencies">
            {hits.map((a) => (
              <Row key={a.id} value={`agency:${a.id}`} icon="apartment" query={query} title={a.name} onRun={() => onRun("/admin")} />
            ))}
          </Command.Group>
        ) : null;
      })()}
      <NotificationResults role={role} query={query} onRun={onRun} />
    </>
  );
}

export function CommandSearchResults({
  role,
  query,
  onRun,
}: {
  role: Role;
  query: string;
  onRun: (href: string) => void;
}) {
  if (role === "employee") return <EmployeeSearch query={query} onRun={onRun} />;
  if (role === "manager") return <ManagerSearch query={query} onRun={onRun} />;
  return <FinanceSearch role={role} query={query} onRun={onRun} />;
}
