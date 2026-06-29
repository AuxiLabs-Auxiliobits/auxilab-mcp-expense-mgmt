"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { signIn } from "next-auth/react";
import { loginSchema, type LoginValues } from "@/lib/schemas";
import { setRememberMe } from "@/lib/session";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { LogoTile } from "@/components/logo";
import { cn } from "@/lib/utils";
import { FeatureCarousel } from "./feature-carousel";
import { AuthThemeToggle } from "./auth-theme-toggle";

const DEMO_ACCOUNTS = [
  { label: "Employee", email: "auxilabs.emp1@demo.local", icon: "person" },
  { label: "Manager", email: "auxilabs.manager@demo.local", icon: "fact_check" },
  { label: "Finance", email: "auxilabs.finance@demo.local", icon: "gavel" },
  { label: "Admin", email: "admin@demo.local", icon: "shield_person" },
];

// Which next-auth provider the SSO button drives (set per-environment).
//   Entra:    NEXT_PUBLIC_SSO_PROVIDER=microsoft-entra-id (default)
//   Keycloak: NEXT_PUBLIC_SSO_PROVIDER=keycloak
const SSO_PROVIDER = process.env.NEXT_PUBLIC_SSO_PROVIDER || "microsoft-entra-id";
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

interface LoginMethods {
  password: boolean;
  sso: boolean;
  sso_label: string;
  sso_reset_url: string;
}

/** Microsoft brand mark (third-party SSO logo). */
function MicrosoftIcon() {
  return (
    <svg viewBox="0 0 21 21" className="h-[18px] w-[18px]" aria-hidden focusable="false">
      <rect x="1" y="1" width="9" height="9" fill="#F25022" />
      <rect x="11" y="1" width="9" height="9" fill="#7FBA00" />
      <rect x="1" y="11" width="9" height="9" fill="#00A4EF" />
      <rect x="11" y="11" width="9" height="9" fill="#FFB900" />
    </svg>
  );
}

export function LoginExperience() {
  const [error, setError] = useState<string | null>(null);
  const [errorKey, setErrorKey] = useState(0); // bump to re-trigger the shake
  const [loading, setLoading] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showDemo, setShowDemo] = useState(false);
  const [remember, setRemember] = useState(false);
  const [methods, setMethods] = useState<LoginMethods | null>(null);

  const busy = loading !== null || success;
  // Default to the local form until the backend tells us the configured methods (db mode).
  const passwordEnabled = methods?.password ?? true;
  const ssoEnabled = methods?.sso ?? false;
  const ssoLabel = methods?.sso_label || "Microsoft";

  function showError(message: string) {
    setError(message);
    setErrorKey((k) => k + 1);
  }

  // Friendly message when redirected here by an expired/ended session.
  useEffect(() => {
    const reason = new URLSearchParams(window.location.search).get("reason");
    if (reason === "expired") {
      showError("Your session has expired. Please sign in again.");
    }
  }, []);

  // Discover which sign-in methods the backend has enabled (local form / SSO).
  useEffect(() => {
    fetch(`${API_BASE}/auth/login-methods`)
      .then((r) => (r.ok ? r.json() : null))
      .then((m: LoginMethods | null) => m && setMethods(m))
      .catch(() => {
        /* keep defaults (local form) if the API is unreachable */
      });
  }, []);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  async function doLogin(email: string, password: string, tag: string) {
    if (busy) return; // prevent duplicate submissions
    setError(null);
    setLoading(tag);
    setRememberMe(remember); // relaxes the idle timeout for this session
    try {
      // Hybrid routing: an Azure-backed account (source="azure") has no local password —
      // send it to Microsoft SSO instead of checking a password. Everyone else (manual /
      // empty / unknown) falls through to the local password check below.
      try {
        const r = await fetch(
          `${API_BASE}/auth/auth-method?email=${encodeURIComponent(email.trim().toLowerCase())}`,
        );
        if (r.ok && (await r.json())?.method === "azure") {
          signIn(SSO_PROVIDER, { callbackUrl: "/" }); // redirects to Microsoft; page navigates away
          return;
        }
      } catch {
        /* if the lookup fails, fall back to local password auth */
      }
      const res = await signIn("credentials", { email, password, redirect: false });
      if (res?.error) {
        // NextAuth v5 beta doesn't reliably propagate CredentialsSignin subclass codes
        // to res.error. On any failure, probe the backend directly to get the real reason.
        let errorMsg = "Incorrect password. Please try again.";
        try {
          const probe = await fetch(`${API_BASE}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password }),
          });
          if (probe.status === 404) errorMsg = "No account found for this email address.";
          else if (probe.status === 403) errorMsg = "This account has been deactivated. Please contact your administrator.";
        } catch { /* keep default message if probe fails */ }
        showError(errorMsg);
        setLoading(null);
        return;
      }
      // Brief success state, then a full navigation so the new session is read
      // and the root route redirects by role.
      setLoading(null);
      setSuccess(true);
      setTimeout(() => {
        window.location.href = "/";
      }, 450);
    } catch {
      showError("Unable to connect. Please try again.");
      setLoading(null);
    }
  }

  function onSso() {
    if (busy) return;
    signIn(SSO_PROVIDER, { callbackUrl: "/" });
  }

  return (
    <div className="relative min-h-screen w-full overflow-hidden bg-background">
      {/* Theme toggle */}
      <div className="absolute right-4 top-4 z-30 animate-fade-in sm:right-6 sm:top-6">
        <AuthThemeToggle />
      </div>

      <div className="grid min-h-screen lg:grid-cols-[1.05fr_minmax(0,1fr)]">
        {/* ── Hero (desktop only) — constant dark brand canvas ────────────────
            The `dark` class scopes the M3 dark tokens to this panel so it stays
            dark in BOTH themes without hardcoding any colors. */}
        <section className="dark noise aurora relative hidden flex-col justify-between overflow-hidden bg-gradient-to-br from-surface-dim via-surface to-background p-10 lg:flex xl:p-14">
          {/* Animated gradients + floating decorative elements */}
          <div aria-hidden className="pointer-events-none absolute inset-0 z-0">
            <div className="absolute -left-24 top-1/4 h-96 w-96 animate-glow-pulse rounded-full bg-primary/25 blur-3xl" />
            <div className="absolute -right-20 bottom-0 h-80 w-80 animate-glow-pulse rounded-full bg-secondary/20 blur-3xl [animation-delay:1.2s]" />
            <div className="absolute left-[12%] top-[16%] h-24 w-24 animate-float rounded-full bg-primary/25 blur-2xl" />
            <div className="absolute right-[18%] top-[28%] h-16 w-16 animate-float rounded-full bg-signal-red/15 blur-2xl [animation-delay:1.5s]" />
            <div className="absolute bottom-[20%] left-[30%] h-20 w-20 animate-float rounded-full bg-secondary/25 blur-2xl [animation-delay:3s]" />
          </div>

          {/* Brand */}
          <div className="relative z-10 flex animate-fade-in items-center gap-3">
            <LogoTile className="h-10 w-10" />
            <div>
              <div className="text-body-lg font-semibold leading-none text-on-surface">Auxilab</div>
              <div className="mt-1 text-label-sm uppercase tracking-wider text-on-surface-variant">
                Expense Management
              </div>
            </div>
          </div>

          {/* Headline + carousel */}
          <div className="relative z-10 max-w-lg">
            <h1 className="animate-slide-up text-[2.75rem] font-bold leading-[1.05] tracking-tight text-on-surface xl:text-[3.25rem]">
              Welcome back to <span className="gradient-text">effortless</span> expense management
            </h1>
            <p className="mt-5 max-w-md animate-slide-up text-body-md text-on-surface-variant [animation-delay:80ms]">
              Submissions, approvals, and compliance — automated, audited, and synced for every
              agency.
            </p>
            <div className="mt-8 animate-slide-up [animation-delay:160ms]">
              <FeatureCarousel />
            </div>
          </div>

          {/* Trust row */}
          <div className="relative z-10 flex animate-fade-in flex-wrap items-center gap-x-6 gap-y-2 text-label-md text-on-surface-variant [animation-delay:240ms]">
            <span className="flex items-center gap-1.5">
              <Icon name="verified_user" className="text-[16px] text-primary" /> SOC 2 Type II
            </span>
            <span className="flex items-center gap-1.5">
              <Icon name="lock" className="text-[16px] text-primary" /> Encrypted in transit
            </span>
            <span className="flex items-center gap-1.5">
              <Icon name="groups" className="text-[16px] text-primary" /> RBAC &amp; audit by default
            </span>
          </div>
        </section>

        {/* ── Authentication ──────────────────────────────────────────────── */}
        <section className="relative flex items-center justify-center p-4 py-10 sm:p-8">
          <div className="w-full max-w-[420px] animate-scale-in">
            {/* Compact brand for tablet/mobile (hero hidden) */}
            <div className="mb-6 flex items-center justify-center gap-2.5 lg:hidden">
              <LogoTile className="h-9 w-9" />
              <div>
                <div className="text-body-lg font-semibold leading-none text-on-surface">Auxilab</div>
                <div className="mt-0.5 text-label-sm uppercase tracking-wider text-on-surface-variant">
                  Expense Management
                </div>
              </div>
            </div>

            {/* Auth card — enhanced glassmorphism + animated gradient edge */}
            <div className="gradient-border rounded-3xl border border-outline-variant/40 bg-surface-container-lowest/70 p-6 shadow-elevation-3 backdrop-blur-2xl sm:p-8">
              <h2 className="text-headline-lg font-semibold text-on-surface">Welcome back</h2>
              <p className="mt-1.5 text-body-sm text-on-surface-variant">
                Sign in to your Auxilab workspace to continue.
              </p>

              {error && (
                <div
                  key={errorKey}
                  role="alert"
                  aria-live="assertive"
                  className="mt-5 flex animate-shake items-start gap-2 rounded-xl border border-error/30 bg-error-container px-3.5 py-3 text-body-sm text-on-error-container"
                >
                  <Icon name="error" className="mt-0.5 shrink-0 text-[18px]" />
                  <span>{error}</span>
                </div>
              )}

              {passwordEnabled && (
              <form
                onSubmit={handleSubmit((v) => doLogin(v.email, v.password, "form"))}
                className="mt-6 space-y-4"
                noValidate
              >
                {/* Email */}
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
                      placeholder="you@company.com"
                      className="pl-10"
                      aria-invalid={!!errors.email}
                      aria-describedby={errors.email ? "email-error" : undefined}
                      {...register("email")}
                    />
                  </div>
                  {errors.email && (
                    <p id="email-error" className="text-label-md text-error">
                      {errors.email.message}
                    </p>
                  )}
                </div>

                {/* Password */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label htmlFor="password" className="block text-body-sm font-medium text-on-surface">
                      Password
                    </label>
                    <Link
                      href="/forgot-password"
                      className="text-label-md font-medium text-secondary hover:underline"
                    >
                      Forgot password?
                    </Link>
                  </div>
                  <div className="group relative">
                    <Icon
                      name="lock"
                      className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[18px] text-on-surface-variant transition-colors group-focus-within:text-primary"
                    />
                    <Input
                      id="password"
                      type={showPassword ? "text" : "password"}
                      autoComplete="current-password"
                      placeholder="••••••••"
                      className="px-10"
                      aria-invalid={!!errors.password}
                      aria-describedby={errors.password ? "password-error" : undefined}
                      {...register("password")}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((v) => !v)}
                      aria-label={showPassword ? "Hide password" : "Show password"}
                      aria-pressed={showPassword}
                      className="absolute right-3 top-1/2 -translate-y-1/2 rounded p-1 text-on-surface-variant transition-colors hover:text-on-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-secondary"
                    >
                      <Icon
                        name={showPassword ? "visibility_off" : "visibility"}
                        className="text-[18px]"
                      />
                    </button>
                  </div>
                  {errors.password && (
                    <p id="password-error" className="text-label-md text-error">
                      {errors.password.message}
                    </p>
                  )}
                </div>

                {/* Remember me */}
                <label className="flex select-none items-center gap-2 text-body-sm text-on-surface-variant">
                  <input
                    type="checkbox"
                    checked={remember}
                    onChange={(e) => setRemember(e.target.checked)}
                    className="h-4 w-4 rounded border-outline-variant text-primary focus:ring-secondary"
                  />
                  Keep me signed in
                </label>

                {/* Submit */}
                <Button
                  type="submit"
                  size="lg"
                  className={cn(
                    "group relative w-full overflow-hidden transition-transform active:scale-[0.99]",
                    loading === "form" && "shimmer",
                    success && "bg-success-green text-on-primary hover:bg-success-green",
                  )}
                  loading={loading === "form"}
                  disabled={busy}
                >
                  {success ? (
                    <span className="flex animate-scale-in items-center gap-2">
                      <Icon name="check_circle" /> Welcome back
                    </span>
                  ) : loading === "form" ? (
                    "Signing you in…"
                  ) : (
                    <>
                      Sign in
                      <Icon
                        name="arrow_forward"
                        className="transition-transform duration-200 group-hover:translate-x-0.5"
                      />
                    </>
                  )}
                </Button>
              </form>
              )}

              {/* SSO (provider-aware: Microsoft Entra / Keycloak / …) */}
              {ssoEnabled && (
                <>
                  {passwordEnabled && (
                    <div className="my-6 flex items-center gap-3">
                      <span className="h-px flex-1 bg-outline-variant" />
                      <span className="text-label-md text-on-surface-variant">or continue with</span>
                      <span className="h-px flex-1 bg-outline-variant" />
                    </div>
                  )}
                  <Button
                    variant={passwordEnabled ? "outline" : "default"}
                    className={cn("w-full", !passwordEnabled && "mt-6")}
                    disabled={busy}
                    onClick={onSso}
                  >
                    {SSO_PROVIDER.includes("entra") ? <MicrosoftIcon /> : <Icon name="vpn_key" />}
                    Continue with {ssoLabel}
                  </Button>
                </>
              )}

              {/* Trust indicator */}
              <div className="mt-6 flex items-center justify-center gap-1.5 text-label-md text-on-surface-variant">
                <Icon name="lock" className="text-[14px]" />
                Encrypted connection · SOC 2 Type II
              </div>
            </div>

            {/* Demo access — local mode only, secondary, behind a disclosure */}
            {passwordEnabled && (
            <div className="mt-5">
              <button
                onClick={() => setShowDemo((v) => !v)}
                aria-expanded={showDemo}
                className="mx-auto flex items-center gap-1 rounded-md px-2 py-1 text-label-md text-on-surface-variant transition-colors hover:text-on-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-secondary"
              >
                <Icon name="science" className="text-[14px]" /> Explore with a demo account
                <Icon name={showDemo ? "expand_less" : "expand_more"} className="text-[16px]" />
              </button>
              {showDemo && (
                <div className="mt-3 grid animate-slide-up grid-cols-2 gap-2 rounded-2xl border border-outline-variant bg-surface-container-low/60 p-3">
                  {DEMO_ACCOUNTS.map((d) => (
                    <button
                      key={d.email}
                      type="button"
                      disabled={busy}
                      onClick={() => doLogin(d.email, "demo", d.email)}
                      className="flex items-center gap-2 rounded-xl border border-outline-variant bg-surface-container-lowest px-3 py-2 text-left text-body-sm transition-colors hover:border-secondary hover:bg-surface-container-low disabled:opacity-50"
                    >
                      <Icon name={d.icon} className="text-[18px] text-primary" />
                      <span className="font-medium text-on-surface">
                        {loading === d.email ? "…" : d.label}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
            )}

            <p className="mt-8 text-center text-label-sm uppercase tracking-wider text-on-surface-variant">
              An Auxiliobits platform
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}
