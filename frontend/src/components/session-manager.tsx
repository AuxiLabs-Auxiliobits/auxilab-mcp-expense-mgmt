"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { signOut, useSession } from "next-auth/react";
import { useQueryClient } from "@tanstack/react-query";
import {
  ABSOLUTE_TIMEOUT_MS,
  IDLE_TIMEOUT_MS,
  WARNING_BEFORE_MS,
  broadcastLogout,
  isRememberMe,
  onLogoutBroadcast,
  setSessionExpiredHandler,
  type LogoutReason,
} from "@/lib/session";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const ACTIVITY_EVENTS = ["mousemove", "mousedown", "keydown", "scroll", "touchstart", "click"] as const;

/** Read the JWT `exp` (ms) without verifying — just for the absolute-expiry deadline. */
function tokenExpMs(token: string | undefined): number | null {
  if (!token) return null;
  try {
    const payload = token.split(".")[1];
    const json = JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")));
    return typeof json.exp === "number" ? json.exp * 1000 : null;
  } catch {
    return null;
  }
}

function mmss(ms: number): string {
  const s = Math.max(0, Math.ceil(ms / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/**
 * Enforces idle + absolute session timeouts with a pre-logout warning, reacts to API 401s,
 * and synchronizes logout across tabs. Mounted once inside the authenticated portal shell.
 */
export function SessionManager() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const qc = useQueryClient();

  const lastActivity = useRef<number>(Date.now());
  const mountedAt = useRef<number>(Date.now());
  const loggingOut = useRef(false);
  const [msLeft, setMsLeft] = useState<number | null>(null); // non-null => warning shown

  const accessToken = (session as { accessToken?: string } | null)?.accessToken;

  const doLogout = useCallback(
    (reason: LogoutReason) => {
      if (loggingOut.current) return;
      loggingOut.current = true;
      broadcastLogout(reason); // tell other tabs
      qc.clear(); // drop all cached API data (permissions, sheets, receipts, …)
      try {
        sessionStorage.clear();
      } catch {
        /* ignore */
      }
      const callbackUrl = reason === "manual" ? "/login" : "/login?reason=expired";
      void signOut({ redirect: true, callbackUrl });
    },
    [qc],
  );

  // 1) API 401 → session expired/revoked (wired from the QueryClient error handler).
  useEffect(() => {
    setSessionExpiredHandler((reason) => doLogout(reason));
    return () => setSessionExpiredHandler(null);
  }, [doLogout]);

  // 2) Another tab logged out → log this tab out too (no re-broadcast).
  useEffect(() => {
    return onLogoutBroadcast(() => {
      if (loggingOut.current) return;
      loggingOut.current = true;
      qc.clear();
      void signOut({ redirect: true, callbackUrl: "/login" });
    });
  }, [qc]);

  // 3) next-auth dropped the session (its own cross-tab sync / cookie gone) → leave the portal.
  useEffect(() => {
    if (status === "unauthenticated" && !loggingOut.current) {
      router.replace("/login");
    }
  }, [status, router]);

  // 4) Track activity (refs only — no re-render per mouse move).
  useEffect(() => {
    const onActivity = () => {
      lastActivity.current = Date.now();
      if (msLeft !== null) setMsLeft(null); // any activity dismisses a pending warning
    };
    for (const ev of ACTIVITY_EVENTS) {
      window.addEventListener(ev, onActivity, { passive: true });
    }
    return () => {
      for (const ev of ACTIVITY_EVENTS) window.removeEventListener(ev, onActivity);
    };
  }, [msLeft]);

  // 5) The ticker: every second, compute the nearest deadline and warn / log out.
  useEffect(() => {
    if (status !== "authenticated") return;
    const tick = () => {
      if (loggingOut.current) return;
      const now = Date.now();
      const absolute = tokenExpMs(accessToken) ?? mountedAt.current + ABSOLUTE_TIMEOUT_MS;
      const idle = isRememberMe() ? Infinity : lastActivity.current + IDLE_TIMEOUT_MS;
      const deadline = Math.min(absolute, idle);
      const remaining = deadline - now;
      if (remaining <= 0) {
        setMsLeft(null);
        doLogout("expired");
      } else if (remaining <= WARNING_BEFORE_MS) {
        setMsLeft(remaining);
      } else if (msLeft !== null) {
        setMsLeft(null);
      }
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [status, accessToken, doLogout, msLeft]);

  function stayLoggedIn() {
    lastActivity.current = Date.now();
    setMsLeft(null);
    // Touch a lightweight endpoint to confirm the token is still valid (and surface a 401 early).
    void qc.invalidateQueries({ queryKey: ["current-user"] });
  }

  return (
    <Dialog open={msLeft !== null} onOpenChange={(o) => !o && stayLoggedIn()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Icon name="schedule" className="text-secondary" /> Still there?
          </DialogTitle>
          <DialogDescription>
            Your session will expire in{" "}
            <span className="font-mono font-semibold text-on-surface">{mmss(msLeft ?? 0)}</span>{" "}
            due to inactivity. Do you want to stay signed in?
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => doLogout("manual")}>
            Log out now
          </Button>
          <Button onClick={stayLoggedIn}>Stay logged in</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
