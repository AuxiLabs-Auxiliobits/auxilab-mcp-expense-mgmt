"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useSessionRole } from "@/components/session-role";
import {
  useAllNotifications,
  useArchiveNotification,
  useDeleteNotification,
  useMarkNotificationsRead,
  useMarkOneNotificationRead,
} from "@/data/hooks";
import {
  Drawer,
  DrawerBody,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { Input } from "@/components/ui/input";
import { Icon } from "@/components/ui/icon";
import { formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";
import {
  BUCKET_ORDER,
  CATEGORY_META,
  CATEGORY_ORDER,
  KIND_CLASS,
  PRIORITY_BAR,
  categoryOf,
  dateBucket,
  priorityOf,
  type NotifCategory,
} from "@/lib/notification-meta";
import {
  DEFAULT_PREFS,
  loadPrefs,
  playChime,
  savePrefs,
  type DigestCadence,
  type NotifPrefs,
} from "@/lib/notification-prefs";
import type { AppNotification } from "@/data/types";

type StatusFilter = "all" | "unread";

export function NotificationBell() {
  const router = useRouter();
  const { sessionRole } = useSessionRole();
  const { data, isLoading, isError } = useAllNotifications(sessionRole);
  const markAll = useMarkNotificationsRead(sessionRole);
  const markOne = useMarkOneNotificationRead(sessionRole);
  const archive = useArchiveNotification(sessionRole);
  const remove = useDeleteNotification(sessionRole);

  const [open, setOpen] = useState(false);
  const [view, setView] = useState<"inbox" | "prefs">("inbox");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [category, setCategory] = useState<NotifCategory | "all">("all");
  const [showArchived, setShowArchived] = useState(false);
  const [prefs, setPrefs] = useState<NotifPrefs>(DEFAULT_PREFS);

  useEffect(() => setPrefs(loadPrefs()), []);

  const all = useMemo(() => data ?? [], [data]);
  const unread = useMemo(() => all.filter((n) => !n.archived && !n.read).length, [all]);

  // Sound on newly-arrived notifications (when enabled).
  const prevUnread = useRef<number | null>(null);
  useEffect(() => {
    if (prevUnread.current !== null && unread > prevUnread.current) {
      if (prefs.channels.sound && prefs.channels.inApp) playChime();
    }
    prevUnread.current = unread;
  }, [unread, prefs.channels.sound, prefs.channels.inApp]);

  const visible = useMemo(() => {
    let list = all.filter((n) => (showArchived ? n.archived : !n.archived));
    if (status === "unread") list = list.filter((n) => !n.read);
    if (category !== "all") list = list.filter((n) => categoryOf(n) === category);
    const q = query.trim().toLowerCase();
    if (q) list = list.filter((n) => `${n.title} ${n.body}`.toLowerCase().includes(q));
    return list;
  }, [all, showArchived, status, category, query]);

  const groups = useMemo(() => {
    const m = new Map<string, AppNotification[]>();
    for (const n of visible) {
      const b = dateBucket(n.timestamp);
      const arr = m.get(b) ?? [];
      arr.push(n);
      m.set(b, arr);
    }
    return BUCKET_ORDER.filter((b) => m.has(b)).map((b) => [b, m.get(b)!] as const);
  }, [visible]);

  function openNotification(n: AppNotification) {
    if (!n.read) markOne.mutate(n.id);
    if (n.href) {
      setOpen(false);
      requestAnimationFrame(() => router.push(n.href!));
    }
  }

  function updatePrefs(next: NotifPrefs) {
    setPrefs(next);
    savePrefs(next);
  }

  return (
    <>
      <button
        onClick={() => {
          setView("inbox");
          setOpen(true);
        }}
        aria-label={`Notifications${unread ? `, ${unread} unread` : ""}`}
        className="relative rounded p-1.5 text-on-surface-variant transition-colors hover:bg-surface-container-high hover:text-primary focus:outline-none focus:ring-1 focus:ring-secondary"
      >
        <Icon name="notifications" />
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-error px-1 text-[10px] font-bold text-on-error">
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>

      <Drawer open={open} onOpenChange={setOpen}>
        <DrawerContent className="w-full sm:max-w-md" aria-label="Notification center">
          <DrawerHeader className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <DrawerTitle>{view === "prefs" ? "Notification settings" : "Notifications"}</DrawerTitle>
              {view === "inbox" && unread > 0 && (
                <span className="rounded-full bg-primary/10 px-2 py-0.5 text-label-md font-medium text-primary">
                  {unread} new
                </span>
              )}
            </div>
            <div className="flex items-center gap-1">
              {view === "inbox" ? (
                <>
                  {unread > 0 && (
                    <button
                      onClick={() => markAll.mutate()}
                      disabled={markAll.isPending}
                      className="rounded-md px-2 py-1 text-label-md font-medium text-secondary hover:bg-surface-container-low disabled:opacity-50"
                    >
                      Mark all read
                    </button>
                  )}
                  <IconBtn name="settings" label="Notification settings" onClick={() => setView("prefs")} />
                </>
              ) : (
                <IconBtn name="arrow_back" label="Back to inbox" onClick={() => setView("inbox")} />
              )}
            </div>
          </DrawerHeader>

          {view === "prefs" ? (
            <PreferencesPanel prefs={prefs} onChange={updatePrefs} />
          ) : (
            <>
              {/* Search + filters */}
              <div className="space-y-2 border-b border-outline-variant px-5 py-3">
                <div className="relative">
                  <Icon
                    name="search"
                    className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[18px] text-on-surface-variant"
                  />
                  <Input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Search notifications…"
                    className="pl-9"
                    aria-label="Search notifications"
                  />
                </div>
                <div className="flex flex-wrap items-center gap-1.5">
                  <Chip active={status === "all" && !showArchived} onClick={() => { setStatus("all"); setShowArchived(false); }}>
                    All
                  </Chip>
                  <Chip active={status === "unread" && !showArchived} onClick={() => { setStatus("unread"); setShowArchived(false); }}>
                    Unread
                  </Chip>
                  <Chip active={showArchived} onClick={() => setShowArchived((v) => !v)}>
                    Archived
                  </Chip>
                  <span className="mx-0.5 h-4 w-px bg-outline-variant" />
                  <Chip active={category === "all"} onClick={() => setCategory("all")}>
                    Any
                  </Chip>
                  {CATEGORY_ORDER.map((c) => (
                    <Chip key={c} active={category === c} onClick={() => setCategory(c)}>
                      {CATEGORY_META[c].label}
                    </Chip>
                  ))}
                </div>
              </div>

              <DrawerBody className="p-0">
                {isLoading ? (
                  <div className="space-y-2 p-4">
                    {[0, 1, 2, 3].map((i) => (
                      <div key={i} className="flex gap-3">
                        <div className="h-8 w-8 shrink-0 animate-pulse rounded-full bg-surface-container-high" />
                        <div className="flex-1 space-y-1.5">
                          <div className="h-3 w-2/3 animate-pulse rounded bg-surface-container-high" />
                          <div className="h-3 w-1/2 animate-pulse rounded bg-surface-container-high" />
                        </div>
                      </div>
                    ))}
                  </div>
                ) : isError ? (
                  <EmptyState icon="error" title="Couldn't load notifications" body="Please try again in a moment." />
                ) : visible.length === 0 ? (
                  <EmptyState
                    icon={showArchived ? "inventory_2" : "notifications_off"}
                    title={showArchived ? "No archived notifications" : "You're all caught up"}
                    body={query || category !== "all" || status === "unread" ? "No notifications match your filters." : "New activity will appear here."}
                  />
                ) : (
                  groups.map(([bucket, items]) => (
                    <div key={bucket}>
                      <div className="sticky top-0 z-10 bg-surface-container-lowest/90 px-5 py-1.5 text-label-sm font-semibold uppercase tracking-wider text-on-surface-variant backdrop-blur">
                        {bucket}
                      </div>
                      {items.map((n) => (
                        <NotificationRow
                          key={n.id}
                          n={n}
                          archivedView={showArchived}
                          onOpen={() => openNotification(n)}
                          onRead={() => markOne.mutate(n.id)}
                          onArchive={() => archive.mutate(n.id)}
                          onDelete={() => remove.mutate(n.id)}
                          readPending={markOne.isPending && markOne.variables === n.id}
                          archivePending={archive.isPending && archive.variables === n.id}
                          deletePending={remove.isPending && remove.variables === n.id}
                        />
                      ))}
                    </div>
                  ))
                )}
              </DrawerBody>
            </>
          )}
        </DrawerContent>
      </Drawer>
    </>
  );
}

function NotificationRow({
  n,
  archivedView,
  onOpen,
  onRead,
  onArchive,
  onDelete,
  readPending,
  archivePending,
  deletePending,
}: {
  n: AppNotification;
  archivedView: boolean;
  onOpen: () => void;
  onRead: () => void;
  onArchive: () => void;
  onDelete: () => void;
  readPending?: boolean;
  archivePending?: boolean;
  deletePending?: boolean;
}) {
  const cat = categoryOf(n);
  const priority = priorityOf(n);
  return (
    <div
      className={cn(
        "group relative flex items-stretch gap-1 border-b border-outline-variant pr-2 transition-colors last:border-0 hover:bg-surface-container-low",
        !n.read && "bg-surface-bright",
      )}
    >
      <span className={cn("w-0.5 shrink-0 rounded-full", PRIORITY_BAR[priority])} aria-hidden />
      <button
        onClick={onOpen}
        className="flex flex-1 items-start gap-3 px-2 py-3 text-left outline-none focus-visible:bg-surface-container-low"
      >
        <span className={cn("mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full", KIND_CLASS[n.kind])}>
          <Icon name={n.icon} className="text-[18px]" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-2">
            <span className={cn("truncate text-body-sm text-on-surface", !n.read && "font-semibold")}>
              {n.title}
            </span>
            {!n.read && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-secondary" aria-label="unread" />}
          </span>
          <span className="line-clamp-2 text-body-sm text-on-surface-variant">{n.body}</span>
          <span className="mt-0.5 flex items-center gap-2 text-label-sm text-on-surface-variant">
            <span className="rounded bg-surface-container-high px-1.5 py-0.5">{CATEGORY_META[cat].label}</span>
            {formatRelative(n.timestamp)}
            {n.href && <Icon name="open_in_new" className="text-[12px]" />}
          </span>
        </span>
      </button>
      <div className="flex flex-col items-center justify-center gap-1 opacity-0 transition-opacity focus-within:opacity-100 group-hover:opacity-100">
        {!n.read && <IconBtn name="done" label="Mark read" small onClick={onRead} loading={readPending} />}
        {!archivedView && <IconBtn name="archive" label="Archive" small onClick={onArchive} loading={archivePending} />}
        <IconBtn name="delete" label="Delete" small onClick={onDelete} loading={deletePending} />
      </div>
    </div>
  );
}

function PreferencesPanel({ prefs, onChange }: { prefs: NotifPrefs; onChange: (p: NotifPrefs) => void }) {
  const channels: { key: keyof NotifPrefs["channels"]; label: string; icon: string }[] = [
    { key: "inApp", label: "In-app", icon: "notifications" },
    { key: "email", label: "Email", icon: "mail" },
    { key: "browser", label: "Browser push", icon: "desktop_windows" },
    { key: "sound", label: "Sound", icon: "volume_up" },
  ];
  const digests: DigestCadence[] = ["instant", "hourly", "daily", "weekly"];
  return (
    <DrawerBody className="space-y-6">
      <section>
        <h3 className="mb-2 text-label-sm font-semibold uppercase tracking-wider text-on-surface-variant">Channels</h3>
        <div className="space-y-1">
          {channels.map((c) => (
            <Toggle
              key={c.key}
              icon={c.icon}
              label={c.label}
              checked={prefs.channels[c.key]}
              onChange={(v) => onChange({ ...prefs, channels: { ...prefs.channels, [c.key]: v } })}
            />
          ))}
        </div>
      </section>
      <section>
        <h3 className="mb-2 text-label-sm font-semibold uppercase tracking-wider text-on-surface-variant">Categories</h3>
        <div className="space-y-1">
          {CATEGORY_ORDER.map((c) => (
            <Toggle
              key={c}
              icon={CATEGORY_META[c].icon}
              label={CATEGORY_META[c].label}
              checked={prefs.categories[c]}
              onChange={(v) => onChange({ ...prefs, categories: { ...prefs.categories, [c]: v } })}
            />
          ))}
        </div>
      </section>
      <section>
        <h3 className="mb-2 text-label-sm font-semibold uppercase tracking-wider text-on-surface-variant">Delivery cadence</h3>
        <div className="grid grid-cols-2 gap-2">
          {digests.map((d) => (
            <button
              key={d}
              onClick={() => onChange({ ...prefs, digest: d })}
              className={cn(
                "rounded-lg border px-3 py-2 text-body-sm capitalize transition-colors",
                prefs.digest === d
                  ? "border-primary bg-primary/10 font-medium text-primary"
                  : "border-outline-variant text-on-surface-variant hover:bg-surface-container-low",
              )}
            >
              {d === "instant" ? "Instant" : `${d} digest`}
            </button>
          ))}
        </div>
        <p className="mt-3 text-label-md text-on-surface-variant">
          In-app and sound apply instantly. Email and digest cadence are saved here and delivered
          by the server when the mailer/scheduler is enabled.
        </p>
      </section>
    </DrawerBody>
  );
}

// ── small UI atoms ──
function Chip({ active, onClick, children }: { active?: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "h-7 rounded-full px-2.5 text-label-md font-medium transition-colors",
        active
          ? "bg-primary text-on-primary"
          : "bg-surface-container-high text-on-surface-variant hover:text-on-surface",
      )}
    >
      {children}
    </button>
  );
}

function IconBtn({
  name,
  label,
  onClick,
  small,
  loading,
}: {
  name: string;
  label: string;
  onClick: () => void;
  small?: boolean;
  loading?: boolean;
}) {
  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        if (!loading) onClick();
      }}
      disabled={loading}
      aria-label={label}
      aria-busy={loading || undefined}
      title={label}
      className={cn(
        "rounded-md p-1.5 text-on-surface-variant transition-colors hover:bg-surface-container-high hover:text-on-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-secondary disabled:pointer-events-none disabled:opacity-50",
        small && "p-1",
      )}
    >
      <Icon
        name={loading ? "progress_activity" : name}
        className={cn(small ? "text-[16px]" : "text-[18px]", loading && "animate-spin")}
      />
    </button>
  );
}

function Toggle({
  icon,
  label,
  checked,
  onChange,
}: {
  icon: string;
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      onClick={() => onChange(!checked)}
      role="switch"
      aria-checked={checked}
      className="flex w-full items-center justify-between rounded-lg px-2 py-2 text-left transition-colors hover:bg-surface-container-low"
    >
      <span className="flex items-center gap-2.5 text-body-sm text-on-surface">
        <Icon name={icon} className="text-[18px] text-on-surface-variant" />
        {label}
      </span>
      <span
        className={cn(
          "relative h-5 w-9 rounded-full transition-colors",
          checked ? "bg-primary" : "bg-surface-container-high",
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 h-4 w-4 rounded-full bg-surface-container-lowest shadow-sm transition-transform",
            checked ? "translate-x-4" : "translate-x-0.5",
          )}
        />
      </span>
    </button>
  );
}

function EmptyState({ icon, title, body }: { icon: string; title: string; body: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-1 px-6 py-16 text-center">
      <Icon name={icon} className="text-[36px] text-on-surface-variant/40" />
      <p className="text-body-sm font-medium text-on-surface">{title}</p>
      <p className="text-body-sm text-on-surface-variant">{body}</p>
    </div>
  );
}
