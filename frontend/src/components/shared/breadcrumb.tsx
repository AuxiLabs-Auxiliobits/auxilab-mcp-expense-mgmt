"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "@/components/ui/icon";

const LABELS: Record<string, string> = {
  employee: "Employee",
  manager: "Manager",
  finance: "Finance",
  admin: "Admin",
  sheets: "Expense Sheets",
  new: "New",
  receipts: "Receipts",
  activity: "Activity",
  settings: "Settings",
  audit: "Audit Log",
  policy: "Agency Policy",
  assistant: "Policy Assistant",
};

function toLabel(seg: string) {
  if (LABELS[seg]) return LABELS[seg];
  // Sheet IDs and other opaque segments render as-is.
  if (/[A-Z]{2}-\d/.test(seg)) return seg;
  return seg.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function Breadcrumb() {
  const pathname = usePathname();
  const segs = pathname.split("/").filter(Boolean);
  if (segs.length <= 1) return null; // top-level page — no breadcrumb needed

  const crumbs = segs.map((seg, i) => ({
    seg,
    href: "/" + segs.slice(0, i + 1).join("/"),
    last: i === segs.length - 1,
  }));

  return (
    <nav aria-label="Breadcrumb" className="mb-1.5">
      <ol className="flex flex-wrap items-center gap-1.5 text-label-md text-on-surface-variant">
        {crumbs.map((c, i) => (
          <li key={c.href} className="flex items-center gap-1.5">
            {i > 0 && <Icon name="chevron_right" className="text-[14px] text-outline" aria-hidden />}
            {c.last ? (
              <span className="font-medium text-on-surface" aria-current="page">
                {toLabel(c.seg)}
              </span>
            ) : (
              <Link href={c.href} className="transition-colors hover:text-on-surface hover:underline">
                {toLabel(c.seg)}
              </Link>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
