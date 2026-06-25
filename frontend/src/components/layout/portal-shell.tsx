"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { roleFromPath } from "@/lib/rbac";
import { cn } from "@/lib/utils";
import { CommandPalette } from "@/components/command-palette";
import { SessionManager } from "@/components/session-manager";
import { AssistantWidget } from "@/features/assistant/assistant-widget";
import { Sidebar } from "./sidebar";
import { TopNav } from "./top-nav";

export function PortalShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const role = roleFromPath(pathname);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  // Close the mobile drawer on navigation.
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  // Restore the collapsed preference.
  useEffect(() => {
    setCollapsed(localStorage.getItem("sidebar-collapsed") === "1");
  }, []);

  function toggleCollapse() {
    setCollapsed((c) => {
      const next = !c;
      localStorage.setItem("sidebar-collapsed", next ? "1" : "0");
      return next;
    });
  }

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar
        role={role}
        collapsed={collapsed}
        onToggleCollapse={toggleCollapse}
        mobileOpen={mobileOpen}
        onClose={() => setMobileOpen(false)}
      />
      <div
        className={cn(
          "flex min-h-screen flex-1 flex-col transition-[margin] duration-200",
          collapsed ? "md:ml-16" : "md:ml-60",
        )}
      >
        <TopNav role={role} onMenuClick={() => setMobileOpen(true)} />
        <main className="flex-1">{children}</main>
      </div>
      <CommandPalette />
      <SessionManager />
      <AssistantWidget role={role} pathname={pathname} />
    </div>
  );
}
