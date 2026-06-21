"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "@/components/ui/icon";
import { LogoTile } from "@/components/logo";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { getNav, PORTAL_BASE } from "@/lib/rbac";
import { cn } from "@/lib/utils";
import type { Role } from "@/data/types";

/** Reveal the label as a right-side tooltip only when the rail is collapsed. */
function Tip({
  show,
  label,
  children,
}: {
  show: boolean;
  label: string;
  children: React.ReactElement;
}) {
  if (!show) return children;
  return (
    <Tooltip>
      <TooltipTrigger asChild>{children}</TooltipTrigger>
      <TooltipContent side="right" sideOffset={8}>
        {label}
      </TooltipContent>
    </Tooltip>
  );
}

export function Sidebar({
  role,
  collapsed = false,
  onToggleCollapse,
  mobileOpen = false,
  onClose,
}: {
  role: Role;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  mobileOpen?: boolean;
  onClose?: () => void;
}) {
  const pathname = usePathname();
  const nav = getNav(role);
  const base = PORTAL_BASE[role];

  function isActive(href: string) {
    if (href === "#") return false;
    if (href === base) return pathname === base;
    return pathname === href || pathname.startsWith(`${href}/`);
  }

  // Collapse is a desktop (md+) affordance; the mobile drawer is always full-width.
  const row =
    "group flex h-10 w-full items-center rounded-md px-3 text-body-sm transition-[background-color,box-shadow,color] duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-secondary";
  const collapsedRow = collapsed ? "md:justify-center md:px-0" : "";
  const label = cn(
    "overflow-hidden whitespace-nowrap transition-[max-width,opacity,margin] duration-200 ml-3 max-w-[170px] opacity-100",
    collapsed && "md:ml-0 md:max-w-0 md:opacity-0",
  );

  return (
    <>
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-deep-onyx/40 backdrop-blur-sm md:hidden"
          onClick={onClose}
          aria-hidden
        />
      )}
      <nav
        aria-label="Primary"
        className={cn(
          "fixed left-0 top-0 z-50 flex h-screen flex-col border-r border-outline-variant bg-surface py-5 transition-[width,transform] duration-200 ease-out md:translate-x-0",
          collapsed ? "w-60 md:w-16" : "w-60",
          mobileOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0",
        )}
      >
        {/* Mobile close */}
        <button
          onClick={onClose}
          className="absolute right-3 top-3 rounded p-1 text-on-surface-variant transition-colors hover:bg-surface-container-low hover:text-on-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-secondary md:hidden"
          aria-label="Close menu"
        >
          <Icon name="close" />
        </button>

        {/* Header — brand + collapse control (collapse is a layout utility, in the header) */}
        <div
          className={cn(
            "mb-4 flex items-center justify-between px-5",
            collapsed && "md:flex-col md:justify-center md:gap-2 md:px-3",
          )}
        >
          <Link
            href={base}
            aria-label="Auxilab home"
            className="flex items-center rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-secondary"
          >
            <LogoTile className="h-9 w-9 shrink-0" />
            <div className={label}>
              <span className="block text-body-md font-semibold leading-none text-on-surface">
                Auxilab
              </span>
              <span className="mt-1 block text-label-md uppercase tracking-wider text-on-surface-variant">
                Expense Management
              </span>
            </div>
          </Link>

          <Tip show={collapsed} label="Expand sidebar">
            <button
              onClick={onToggleCollapse}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              aria-expanded={!collapsed}
              className="hidden h-8 w-8 shrink-0 items-center justify-center rounded-md text-on-surface-variant transition-colors hover:bg-surface-container-low hover:text-on-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-secondary md:inline-flex"
            >
              <Icon
                name="chevron_left"
                className={cn("text-[18px] transition-transform duration-200", collapsed && "rotate-180")}
              />
            </button>
          </Tip>
        </div>

        {/* Grouped navigation (enterprise sectioned pattern) */}
        <div className="flex-1 overflow-y-auto px-3">
          {nav.map((group, gi) => (
            <div
              key={group.title ?? `group-${gi}`}
              className={cn(
                gi > 0 && "mt-3",
                // When collapsed on desktop, the section header is hidden, so add a
                // hairline separator to keep groups visually distinct.
                gi > 0 && collapsed && "md:mt-2 md:border-t md:border-outline-variant md:pt-2",
              )}
            >
              {group.title && (
                <p
                  className={cn(
                    "px-3 pb-1 pt-1 text-label-sm font-semibold uppercase tracking-wider text-on-surface-variant/80",
                    collapsed && "md:hidden",
                  )}
                >
                  {group.title}
                </p>
              )}
              <ul className="space-y-0.5">
                {group.items.map((item) => {
                  const active = isActive(item.href);
                  return (
                    <li key={item.label}>
                      <Tip show={collapsed} label={item.label}>
                        <Link
                          href={item.href}
                          aria-label={item.label}
                          aria-current={active ? "page" : undefined}
                          className={cn(
                            row,
                            collapsedRow,
                            active
                              ? "bg-primary-fixed/60 font-semibold text-on-surface shadow-[inset_3px_0_0_rgb(var(--primary))]"
                              : "font-medium text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface",
                          )}
                        >
                          <Icon
                            name={item.icon}
                            filled={active}
                            className={cn(
                              "shrink-0 text-[18px] transition-colors duration-150",
                              active ? "text-primary" : "text-on-surface-variant group-hover:text-on-surface",
                            )}
                          />
                          <span className={label}>{item.label}</span>
                        </Link>
                      </Tip>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
      </nav>
    </>
  );
}
