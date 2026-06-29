/**
 * Client session-lifetime policy + cross-tab coordination.
 *
 * The access token lives in next-auth's encrypted, HttpOnly session cookie (not localStorage),
 * so this module only governs *when* to end the session, not where the token is stored:
 *   • idle timeout  — the ONLY clock-based logout: 10 minutes of inactivity.
 *                     An active user is never logged out (no absolute cap), as long
 *                     as their token keeps refreshing (handled by the auth layer).
 *   • a 401 from any API call → treat as an expired/revoked session (refresh failed)
 *   • multi-tab     — a logout in one tab logs out all tabs
 */

export const IDLE_TIMEOUT_MS = 10 * 60 * 1000; // 10 minutes of inactivity → expire
export const WARNING_BEFORE_MS = 60 * 1000; // warn 1 minute before the idle logout
// No absolute cap: an active session never expires on a clock. Kept for any
// external reference, but the SessionManager no longer enforces it.
export const ABSOLUTE_TIMEOUT_MS = Infinity;

export const REMEMBER_ME_KEY = "expense.rememberMe";

export type LogoutReason = "expired" | "manual" | "revoked";

/** "Remember me" relaxes the idle timeout (absolute cap still applies). */
export function isRememberMe(): boolean {
  try {
    return localStorage.getItem(REMEMBER_ME_KEY) === "1";
  } catch {
    return false;
  }
}
export function setRememberMe(on: boolean): void {
  try {
    if (on) localStorage.setItem(REMEMBER_ME_KEY, "1");
    else localStorage.removeItem(REMEMBER_ME_KEY);
  } catch {
    /* storage unavailable (private mode) — fall back to default timeout */
  }
}

// ── Global "session expired" signal ──────────────────────────────────────────
// The API layer (QueryClient error handler) runs outside React; it calls
// triggerSessionExpired() on a 401, and the mounted SessionManager performs the
// actual logout (clear caches + signOut + redirect).
let expiredHandler: ((reason: LogoutReason) => void) | null = null;

export function setSessionExpiredHandler(fn: ((reason: LogoutReason) => void) | null): void {
  expiredHandler = fn;
}
export function triggerSessionExpired(reason: LogoutReason = "expired"): void {
  expiredHandler?.(reason);
}

// ── Cross-tab logout broadcast ───────────────────────────────────────────────
const CHANNEL = "expense-session";

export function broadcastLogout(reason: LogoutReason): void {
  try {
    const bc = new BroadcastChannel(CHANNEL);
    bc.postMessage({ type: "logout", reason });
    bc.close();
  } catch {
    // BroadcastChannel unsupported → fall back to a storage event other tabs can see.
    try {
      localStorage.setItem("expense.logout", `${reason}:${Date.now()}`);
    } catch {
      /* ignore */
    }
  }
}

/** Subscribe to logout events from other tabs. Returns an unsubscribe fn. */
export function onLogoutBroadcast(cb: (reason: LogoutReason) => void): () => void {
  let bc: BroadcastChannel | null = null;
  try {
    bc = new BroadcastChannel(CHANNEL);
    bc.onmessage = (e) => {
      if (e.data?.type === "logout") cb(e.data.reason ?? "manual");
    };
  } catch {
    /* fall through to storage events */
  }
  const onStorage = (e: StorageEvent) => {
    if (e.key === "expense.logout" && e.newValue) cb("manual");
  };
  window.addEventListener("storage", onStorage);
  return () => {
    bc?.close();
    window.removeEventListener("storage", onStorage);
  };
}
