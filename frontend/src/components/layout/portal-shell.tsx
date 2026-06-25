"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { roleFromPath } from "@/lib/rbac";
import { cn } from "@/lib/utils";
import { Spinner } from "@/components/ui/spinner";
import { LogoTile } from "@/components/logo";
import { CommandPalette } from "@/components/command-palette";
import { SessionManager } from "@/components/session-manager";
import { AssistantWidget } from "@/features/assistant/assistant-widget";
import { Sidebar } from "./sidebar";
import { TopNav } from "./top-nav";

/** Branded full-screen loader shown while the session is being confirmed. */
function SessionGate() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background">
      <LogoTile className="h-11 w-11 shadow-xs" />
      <Spinner size="md" />
      <span className="sr-only">Loading…</span>
    </div>
  );
}

export function PortalShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { status } = useSession();
  const role = roleFromPath(pathname);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  // Client-side guard: the server/middleware can let a request through before
  // the client has confirmed the session. Until `useSession` resolves to
  // `authenticated`, never paint the portal — otherwise a stale session flashes
  // the dashboard for a beat before being bounced. On `unauthenticated`, route
  // to /login ourselves so the bounce is immediate and deterministic.
  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace("/login");
    }
  }, [status, router]);

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

  // Loading, or unauthenticated (redirect in flight) → never show the portal.
  if (status !== "authenticated") {
    return <SessionGate />;
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
