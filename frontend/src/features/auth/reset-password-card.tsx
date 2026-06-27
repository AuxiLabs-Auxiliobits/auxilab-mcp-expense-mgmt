"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { BackToSignIn } from "./auth-card-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

// Mirrors the backend complexity policy (app.services.password_reset_service.validate_password).
const RULES: { label: string; test: (p: string) => boolean }[] = [
  { label: "At least 10 characters", test: (p) => p.length >= 10 },
  { label: "An uppercase letter", test: (p) => /[A-Z]/.test(p) },
  { label: "A lowercase letter", test: (p) => /[a-z]/.test(p) },
  { label: "A number", test: (p) => /\d/.test(p) },
];

export function ResetPasswordCard() {
  const token = useSearchParams().get("token") ?? "";
  const [pw, setPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [show, setShow] = useState(false);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const allPass = RULES.every((r) => r.test(pw));
  const match = pw.length > 0 && pw === confirm;
  const canSubmit = !!token && allPass && match && !loading;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/auth/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: pw }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(data.detail || "This reset link is invalid or has expired.");
        return;
      }
      setDone(true);
    } catch {
      setError("Unable to connect. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <div>
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-error/15 text-error">
          <Icon name="link_off" className="text-[26px]" />
        </div>
        <h1 className="mt-4 text-headline-lg font-semibold text-on-surface">Invalid reset link</h1>
        <p className="mt-2 text-body-sm text-on-surface-variant">
          This link is missing or malformed. Please request a new password reset.
        </p>
        <a
          href="/forgot-password"
          className="mt-6 flex items-center justify-center gap-1 text-label-md font-medium text-secondary hover:underline"
        >
          <Icon name="refresh" className="text-[16px]" /> Request a new link
        </a>
      </div>
    );
  }

  if (done) {
    return (
      <div>
        <div className="flex h-12 w-12 animate-scale-in items-center justify-center rounded-2xl bg-success-green/15 text-success-green">
          <Icon name="check_circle" className="text-[26px]" />
        </div>
        <h1 className="mt-4 text-headline-lg font-semibold text-on-surface">Password updated</h1>
        <p className="mt-2 text-body-sm text-on-surface-variant">
          Your password has been reset. You can now sign in with your new password.
        </p>
        <Button asChild size="lg" className="mt-6 w-full">
          <a href="/login">
            Continue to sign in <Icon name="arrow_forward" />
          </a>
        </Button>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-headline-lg font-semibold text-on-surface">Set a new password</h1>
      <p className="mt-1.5 text-body-sm text-on-surface-variant">
        Choose a strong password you don&apos;t use anywhere else.
      </p>

      {error && (
        <div
          role="alert"
          aria-live="assertive"
          className="mt-5 flex animate-shake items-start gap-2 rounded-xl border border-error/30 bg-error-container px-3.5 py-3 text-body-sm text-on-error-container"
        >
          <Icon name="error" className="mt-0.5 shrink-0 text-[18px]" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={submit} className="mt-6 space-y-4" noValidate>
        <div className="space-y-1.5">
          <label htmlFor="pw" className="block text-body-sm font-medium text-on-surface">
            New password
          </label>
          <div className="group relative">
            <Icon
              name="lock"
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[18px] text-on-surface-variant transition-colors group-focus-within:text-primary"
            />
            <Input
              id="pw"
              type={show ? "text" : "password"}
              autoComplete="new-password"
              autoFocus
              placeholder="••••••••••"
              className="px-10"
              value={pw}
              onChange={(e) => setPw(e.target.value)}
              aria-describedby="pw-rules"
            />
            <button
              type="button"
              onClick={() => setShow((v) => !v)}
              aria-label={show ? "Hide password" : "Show password"}
              aria-pressed={show}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-on-surface-variant transition-colors hover:text-on-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-secondary"
            >
              <Icon name={show ? "visibility_off" : "visibility"} className="text-[18px]" />
            </button>
          </div>
        </div>

        {/* Live complexity checklist */}
        <ul id="pw-rules" className="grid grid-cols-2 gap-1.5">
          {RULES.map((r) => {
            const ok = r.test(pw);
            return (
              <li
                key={r.label}
                className={cn(
                  "flex items-center gap-1.5 text-label-md transition-colors",
                  ok ? "text-success-green" : "text-on-surface-variant",
                )}
              >
                <Icon name={ok ? "check_circle" : "radio_button_unchecked"} className="text-[14px]" />
                {r.label}
              </li>
            );
          })}
        </ul>

        <div className="space-y-1.5">
          <label htmlFor="confirm" className="block text-body-sm font-medium text-on-surface">
            Confirm password
          </label>
          <div className="group relative">
            <Icon
              name="lock"
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[18px] text-on-surface-variant transition-colors group-focus-within:text-primary"
            />
            <Input
              id="confirm"
              type={show ? "text" : "password"}
              autoComplete="new-password"
              placeholder="••••••••••"
              className="pl-10"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              aria-invalid={confirm.length > 0 && !match}
            />
          </div>
          {confirm.length > 0 && !match && (
            <p className="text-label-md text-error">Passwords don&apos;t match.</p>
          )}
        </div>

        <Button type="submit" size="lg" className="w-full" loading={loading} disabled={!canSubmit}>
          {loading ? (
            "Updating…"
          ) : (
            <>
              Reset password <Icon name="arrow_forward" />
            </>
          )}
        </Button>
      </form>

      <BackToSignIn />
    </div>
  );
}
