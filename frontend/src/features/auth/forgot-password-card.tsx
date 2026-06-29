"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { BackToSignIn } from "./auth-card-shell";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

interface LoginMethods {
  password: boolean;
  sso: boolean;
  sso_label: string;
  sso_reset_url: string;
}

export function ForgotPasswordCard() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [methods, setMethods] = useState<LoginMethods | null>(null);

  // Detect SSO-only orgs → local reset isn't applicable.
  useEffect(() => {
    fetch(`${API_BASE}/auth/login-methods`)
      .then((r) => (r.ok ? r.json() : null))
      .then((m: LoginMethods | null) => m && setMethods(m))
      .catch(() => {});
  }, []);

  async function submit(e: React.SyntheticEvent) {
    e.preventDefault();
    if (loading) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/auth/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({})) as { detail?: string };
        setError(body.detail ?? "Unable to send reset link. Please try again.");
        return;
      }
      await res.json().catch(() => {});
      setSent(true);
    } catch {
      setError("Unable to connect. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  // SSO-only: passwords live at the identity provider, not here.
  if (methods && !methods.password && methods.sso) {
    return (
      <div>
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/15 text-primary">
          <Icon name="shield_person" className="text-[26px]" />
        </div>
        <h1 className="mt-4 text-headline-lg font-semibold text-on-surface">Single sign-on</h1>
        <p className="mt-2 text-body-sm text-on-surface-variant">
          Your organization signs in with {methods.sso_label}. Passwords are managed by your
          identity provider — not Auxilab.
        </p>
        {methods.sso_reset_url && (
          <Button asChild className="mt-6 w-full">
            <a href={methods.sso_reset_url} target="_blank" rel="noreferrer">
              <Icon name="open_in_new" /> Reset at {methods.sso_label}
            </a>
          </Button>
        )}
        <BackToSignIn />
      </div>
    );
  }

  if (sent) {
    return (
      <div>
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-success-green/15 text-success-green">
          <Icon name="mark_email_read" className="text-[26px]" />
        </div>
        <h1 className="mt-4 text-headline-lg font-semibold text-on-surface">Check your email</h1>
        <p className="mt-2 text-body-sm text-on-surface-variant">
          If an account exists for <span className="font-medium text-on-surface">{email}</span>, a
          password-reset link is on its way. It is valid for 24 hours and can be used once.
        </p>

        <BackToSignIn />
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-headline-lg font-semibold text-on-surface">Reset your password</h1>
      <p className="mt-1.5 text-body-sm text-on-surface-variant">
        Enter your work email and we&apos;ll send you a secure reset link.
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
          <label htmlFor="email" className="block text-body-sm font-medium text-on-surface">
            Work email
          </label>
          <div className="group relative">
            <Icon
              name="mail"
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[18px] text-on-surface-variant transition-colors group-focus-within:text-primary"
            />
            <Input
              id="email"
              type="email"
              autoComplete="email"
              autoFocus
              required
              placeholder="you@company.com"
              className="pl-10"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
        </div>
        <Button type="submit" size="lg" className="w-full" loading={loading} disabled={loading || !email}>
          {loading ? (
            "Sending…"
          ) : (
            <>
              Send reset link <Icon name="arrow_forward" />
            </>
          )}
        </Button>
      </form>

      <BackToSignIn />
    </div>
  );
}
