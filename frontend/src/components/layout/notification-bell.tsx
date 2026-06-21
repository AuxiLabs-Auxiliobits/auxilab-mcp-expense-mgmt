"use client";

import Link from "next/link";
import { useMarkNotificationsRead, useNotifications } from "@/data/hooks";
import { useSessionRole } from "@/components/session-role";
import { Icon } from "@/components/ui/icon";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { NotificationKind } from "@/data/types";

const KIND_CLASS: Record<NotificationKind, string> = {
  success: "text-success-green bg-success-green/10",
  warning: "text-yellow-600 bg-yellow-500/10",
  error: "text-error bg-error-container",
  info: "text-tertiary bg-tertiary/10",
};

export function NotificationBell() {
  const { sessionRole } = useSessionRole();
  const { data: notifications } = useNotifications(sessionRole);
  const markRead = useMarkNotificationsRead(sessionRole);

  const items = notifications ?? [];
  const unread = items.filter((n) => !n.read).length;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label="Notifications"
        className="relative rounded p-1.5 text-on-surface-variant transition-colors hover:bg-surface-container-high hover:text-primary focus:outline-none focus:ring-1 focus:ring-secondary"
      >
        <Icon name="notifications" />
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-error px-1 text-[10px] font-bold text-on-error">
            {unread}
          </span>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80 p-0">
        <div className="flex items-center justify-between border-b border-outline-variant px-3 py-2.5">
          <span className="text-body-sm font-semibold text-on-surface">Notifications</span>
          {unread > 0 && (
            <button
              onClick={() => markRead.mutate()}
              className="font-mono text-label-md text-secondary hover:underline"
            >
              Mark all read
            </button>
          )}
        </div>
        <div className="max-h-96 overflow-y-auto">
          {items.length === 0 ? (
            <p className="px-3 py-8 text-center text-body-sm text-on-surface-variant">
              You&apos;re all caught up.
            </p>
          ) : (
            items.map((n) => (
              <Link
                key={n.id}
                href={n.href ?? "#"}
                className={cn(
                  "flex gap-3 border-b border-outline-variant px-3 py-3 transition-colors last:border-0 hover:bg-surface-container-low",
                  !n.read && "bg-surface-bright",
                )}
              >
                <span
                  className={cn(
                    "mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
                    KIND_CLASS[n.kind],
                  )}
                >
                  <Icon name={n.icon} className="text-[18px]" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-body-sm font-medium text-on-surface">{n.title}</span>
                    {!n.read && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-secondary" />}
                  </div>
                  <p className="text-body-sm text-on-surface-variant">{n.body}</p>
                  <p className="mt-0.5 font-mono text-label-sm text-on-surface-variant">
                    {formatRelative(n.timestamp)}
                  </p>
                </div>
              </Link>
            ))
          )}
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
