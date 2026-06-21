"use client";

import Link from "next/link";
import { ROLE_LABELS, type Role } from "@/data/types";
import { PORTAL_BASE } from "@/lib/rbac";
import { useSessionRole } from "@/components/session-role";
import { cn } from "@/lib/utils";

const ORDER: Role[] = ["employee", "manager", "finance", "admin"];

/**
 * Role view switcher (top nav). Only admin — which holds full platform rights
 * (SCOPING.md §3) — gets a switcher, across all four views. Every other role
 * has a single view, so the switcher is hidden entirely (no role label shown).
 */
export function RoleSwitcher({ role }: { role: Role }) {
  const { sessionRole } = useSessionRole();
  const visible =
    sessionRole === "admin" ? ORDER : ORDER.filter((r) => r === sessionRole);

  if (visible.length <= 1) return null;

  return (
    <div className="hidden items-center gap-1 rounded border border-outline-variant bg-surface-container-lowest p-1 lg:flex">
      {visible.map((r) => {
        const active = r === role;
        return (
          <Link
            key={r}
            href={PORTAL_BASE[r]}
            className={cn(
              "rounded px-4 py-1.5 text-body-sm transition-all duration-200",
              active
                ? "border border-outline-variant bg-surface-container-low font-semibold text-secondary shadow-sm"
                : "border border-transparent text-on-surface-variant hover:text-secondary",
            )}
          >
            {ROLE_LABELS[r]} View
          </Link>
        );
      })}
    </div>
  );
}
