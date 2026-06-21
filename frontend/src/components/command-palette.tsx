"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Command } from "cmdk";
import { useTheme } from "next-themes";
import { signOut } from "next-auth/react";
import { useSessionRole } from "@/components/session-role";
import { ROLE_LABELS, type Role } from "@/data/types";
import { can, getNav, PORTAL_BASE } from "@/lib/rbac";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Icon } from "@/components/ui/icon";

const PORTAL_META: Record<Role, { label: string; icon: string }> = {
  employee: { label: "Employee Dashboard", icon: "dashboard" },
  manager: { label: "Manager Review Queue", icon: "fact_check" },
  finance: { label: "Finance Console", icon: "gavel" },
  admin: { label: "Admin Settings", icon: "settings" },
};

export const OPEN_COMMAND_EVENT = "auxilab:open-command";

function Item({
  onSelect,
  icon,
  children,
  shortcut,
}: {
  onSelect: () => void;
  icon: string;
  children: React.ReactNode;
  shortcut?: string;
}) {
  return (
    <Command.Item
      onSelect={onSelect}
      className="flex cursor-pointer items-center gap-3 rounded px-2 py-2 text-body-sm text-on-surface outline-none transition-colors data-[selected=true]:bg-surface-container-low"
    >
      <Icon name={icon} className="text-[18px] text-on-surface-variant" />
      <span className="flex-1">{children}</span>
      {shortcut && (
        <span className="font-mono text-label-sm text-on-surface-variant">{shortcut}</span>
      )}
    </Command.Item>
  );
}

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const { setTheme, resolvedTheme } = useTheme();
  const { sessionRole } = useSessionRole();
  // Each user navigates only to their own portal; admin can reach all four.
  const accessible: Role[] =
    sessionRole === "admin"
      ? ["employee", "manager", "finance", "admin"]
      : [sessionRole];

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    }
    function onOpenEvent() {
      setOpen(true);
    }
    document.addEventListener("keydown", onKey);
    window.addEventListener(OPEN_COMMAND_EVENT, onOpenEvent);
    return () => {
      document.removeEventListener("keydown", onKey);
      window.removeEventListener(OPEN_COMMAND_EVENT, onOpenEvent);
    };
  }, []);

  function run(fn: () => void) {
    setOpen(false);
    // let the dialog close before navigating
    requestAnimationFrame(fn);
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-xl gap-0 overflow-hidden p-0">
        <DialogTitle className="sr-only">Command menu</DialogTitle>
        <Command
          loop
          className="[&_[cmdk-input-wrapper]]:border-b [&_[cmdk-input-wrapper]]:border-outline-variant"
        >
          <div className="flex items-center gap-2 border-b border-outline-variant px-4">
            <Icon name="search" className="text-[18px] text-on-surface-variant" />
            <Command.Input
              autoFocus
              placeholder="Type a command or search…"
              className="h-12 flex-1 bg-transparent text-body-md text-on-surface placeholder:text-on-surface-variant/60 focus:outline-none"
            />
            <kbd className="rounded border border-outline-variant px-1.5 py-0.5 font-mono text-label-sm text-on-surface-variant">
              ESC
            </kbd>
          </div>
          <Command.List className="max-h-[60vh] overflow-y-auto p-2">
            <Command.Empty className="px-2 py-8 text-center text-body-sm text-on-surface-variant">
              No results found.
            </Command.Empty>

            <Command.Group heading="Navigate">
              {accessible.map((role) => (
                <Item
                  key={role}
                  icon={PORTAL_META[role].icon}
                  onSelect={() => run(() => router.push(PORTAL_BASE[role]))}
                >
                  {PORTAL_META[role].label}
                  <span className="ml-2 font-mono text-label-sm text-on-surface-variant">
                    {ROLE_LABELS[role]}
                  </span>
                </Item>
              ))}
              <Item icon="description" onSelect={() => run(() => router.push("/employee/sheets"))}>
                My Expense Sheets
              </Item>
            </Command.Group>

            <Command.Group heading="Pages">
              {getNav(sessionRole)
                .flatMap((g) => g.items)
                .map((item) => (
                  <Item
                    key={item.href}
                    icon={item.icon}
                    onSelect={() => run(() => router.push(item.href))}
                  >
                    {item.label}
                  </Item>
                ))}
            </Command.Group>

            <Command.Group heading="Actions">
              {can(sessionRole, "submit_sheet") && (
                <Item
                  icon="add"
                  shortcut="N"
                  onSelect={() => run(() => router.push("/employee/sheets/new"))}
                >
                  New Expense Sheet
                </Item>
              )}
              <Item
                icon={resolvedTheme === "dark" ? "light_mode" : "dark_mode"}
                onSelect={() => run(() => setTheme(resolvedTheme === "dark" ? "light" : "dark"))}
              >
                Toggle {resolvedTheme === "dark" ? "light" : "dark"} theme
              </Item>
            </Command.Group>

            <Command.Group heading="Account">
              <Item icon="logout" onSelect={() => run(() => signOut({ redirectTo: "/login" }))}>
                Sign out
              </Item>
            </Command.Group>
          </Command.List>
        </Command>
      </DialogContent>
    </Dialog>
  );
}
