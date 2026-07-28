/**
 * Notification preferences (Phase 7), persisted per-browser in localStorage.
 *
 * In-app + sound are applied client-side immediately. Email / browser-push and digest
 * cadence are persisted here as the user's intent; honoring them end-to-end needs the
 * delivery side (SMTP — already available via the backend EmailSender — and a scheduler /
 * Web Push), which is wired separately. The store is the single source of truth either way.
 */
import type { NotifCategory } from "@/lib/notification-meta";

export type DigestCadence = "instant" | "hourly" | "daily" | "weekly";

export interface NotifPrefs {
  channels: { inApp: boolean; email: boolean; browser: boolean; sound: boolean };
  categories: Record<NotifCategory, boolean>; // true = enabled, false = muted
  digest: DigestCadence;
}

export const DEFAULT_PREFS: NotifPrefs = {
  channels: { inApp: true, email: true, browser: false, sound: false },
  categories: { expenses: true, approvals: true, finance: true, ai: true, security: true, system: true },
  digest: "instant",
};

const KEY = "auxilab.notif.prefs.v1";

export function loadPrefs(): NotifPrefs {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) || "{}");
    return {
      channels: { ...DEFAULT_PREFS.channels, ...(raw.channels ?? {}) },
      categories: { ...DEFAULT_PREFS.categories, ...(raw.categories ?? {}) },
      digest: (raw.digest as DigestCadence) ?? DEFAULT_PREFS.digest,
    };
  } catch {
    return DEFAULT_PREFS;
  }
}

export function savePrefs(p: NotifPrefs): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(p));
  } catch {
    /* storage unavailable — preferences just won't persist */
  }
}

/** Short, asset-free chime via WebAudio for the "sound" channel. */
export function playChime(): void {
  try {
    const Ctx =
      window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const ctx = new Ctx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.type = "sine";
    osc.frequency.value = 880;
    gain.gain.setValueAtTime(0.0001, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.15, ctx.currentTime + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.25);
    osc.start();
    osc.stop(ctx.currentTime + 0.26);
    osc.onended = () => ctx.close();
  } catch {
    /* audio blocked — ignore */
  }
}
