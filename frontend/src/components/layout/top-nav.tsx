"use client";

import Link from "next/link";
import { signOut, useSession } from "next-auth/react";
import { ROLE_LABELS, type Role } from "@/data/types";
import { cn } from "@/lib/utils";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Icon } from "@/components/ui/icon";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { broadcastLogout, setRememberMe } from "@/lib/session";
import { OPEN_COMMAND_EVENT } from "@/components/command-palette";
import { NotificationBell } from "./notification-bell";
import { ThemeToggle } from "./theme-toggle";

function openCommandPalette() {
  window.dispatchEvent(new Event(OPEN_COMMAND_EVENT));
}

/** Icon-only control; shows a tooltip when `label` is provided. */
function IconButton({
  name,
  label,
  onClick,
  className,
}: {
  name: string;
  label?: string;
  onClick?: () => void;
  className?: string;
}) {
  const button = (
    <button
      onClick={onClick}
      aria-label={label}
      className={cn(
        "relative rounded p-1.5 text-on-surface-variant transition-all duration-200 hover:bg-surface-container-high hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-secondary active:scale-90",
        className,
      )}
    >
      <Icon name={name} />
    </button>
  );
  if (!label) return button;
  return (
    <Tooltip>
      <TooltipTrigger asChild>{button}</TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}

export function TopNav({
  role,
  onMenuClick,
}: {
  role: Role;
  onMenuClick?: () => void;
}) {
  const { data: session } = useSession();
  const user = session?.user;
  const signedInRole = (user?.role ?? role) as Role;
  const name = user?.name ?? "—";
  const agencyName = user?.agencyName;
  const initials = name
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  // Account links — role-aware, only real pages (no dead links).
  const settingsHref =
    signedInRole === "employee"
      ? "/employee/settings"
      : signedInRole === "admin"
        ? "/admin"
        : null;
  const activityHref =
    signedInRole === "employee"
      ? "/employee/activity"
      : signedInRole === "manager"
        ? "/manager/audit"
        : "/finance/audit"; // finance + admin

  return (
    <header className="sticky top-0 z-40 flex h-16 w-full items-center gap-3 border-b border-outline-variant bg-surface/80 px-gutter backdrop-blur-md supports-[backdrop-filter]:bg-surface/60">
      {/* Left — mobile menu only (sidebar owns desktop nav) */}
      <div className="flex items-center md:hidden">
        <IconButton name="menu" label="Menu" onClick={onMenuClick} />
      </div>

      {/* Center — global search */}
      <div className="flex flex-1 justify-center">
        <button
          onClick={openCommandPalette}
          aria-label="Search or jump to"
          className="flex h-10 w-full max-w-md items-center gap-2 rounded-md border border-outline-variant bg-surface-container-lowest px-3 text-left text-body-sm text-on-surface-variant transition-all duration-200 hover:border-secondary hover:shadow-xs"
        >
          <Icon name="search" className="text-[18px]" />
          <span className="flex-1 truncate">Search or jump to…</span>
          <kbd className="hidden shrink-0 rounded border border-outline-variant px-1.5 py-0.5 font-mono text-label-sm sm:block">
            ⌘K
          </kbd>
        </button>
      </div>

      {/* Right — actions (each role sees only its own portal, so no view switcher) */}
      <div className="flex items-center gap-1.5 sm:gap-2">
        <ThemeToggle />
        <NotificationBell />
        <div className="mx-1 hidden h-8 w-px bg-outline-variant sm:block" />
        <DropdownMenu>
          <DropdownMenuTrigger className="rounded-full focus:outline-none focus:ring-1 focus:ring-secondary">
            <Avatar>
              {user?.image && <AvatarImage src={user.image} alt={name} />}
              <AvatarFallback>{initials || "AU"}</AvatarFallback>
            </Avatar>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>
              {/* Row 1: name · Row 2: email · Row 3: role + agency */}
              <div className="font-sans text-body-sm font-semibold normal-case text-on-surface">
                {name}
              </div>
              <div className="font-sans text-label-md normal-case text-on-surface-variant">
                {user?.email}
              </div>
              <div className="mt-1 text-label-sm uppercase text-secondary">
                {ROLE_LABELS[signedInRole]}
                {/* Admins span every agency, so never pin them to one. */}
                {signedInRole === "admin"
                  ? " · All Agencies"
                  : agencyName
                    ? ` · ${agencyName}`
                    : ""}
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            {settingsHref && (
              <DropdownMenuItem asChild>
                <Link href={settingsHref}>
                  <Icon name="settings" /> Settings
                </Link>
              </DropdownMenuItem>
            )}
            <DropdownMenuItem asChild>
              <Link href={activityHref}>
                <Icon name="history" /> My activity
              </Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={() => {
                setRememberMe(false);
                broadcastLogout("manual"); // sign out every tab
                signOut({ redirectTo: "/login" });
              }}
              className="text-error focus:bg-error-container"
            >
              <Icon name="logout" /> Sign Out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
