"use client";

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { signIn } from "next-auth/react";
import { loginSchema, type LoginValues } from "@/lib/schemas";
import { setRememberMe } from "@/lib/session";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { LogoTile } from "@/components/logo";

const DEMO_ACCOUNTS = [
  { label: "Employee", email: "employee@demo.local", icon: "person" },
  { label: "Manager", email: "manager@demo.local", icon: "fact_check" },
  { label: "Finance", email: "finance@demo.local", icon: "gavel" },
  { label: "Admin", email: "admin@demo.local", icon: "shield_person" },
];

const ENTRA_ENABLED = process.env.NEXT_PUBLIC_ENTRA_ENABLED === "true";

export default function LoginPage() {
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [showDemo, setShowDemo] = useState(false);
  const [remember, setRemember] = useState(false);

  // Show a friendly message when redirected here by an expired/ended session.
  useEffect(() => {
    const reason = new URLSearchParams(window.location.search).get("reason");
    if (reason === "expired") {
      setError("Your session has expired. Please sign in again.");
    }
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
    setError(null);
    setLoading(tag);
    setRememberMe(remember); // relaxes the idle timeout for this session
    const res = await signIn("credentials", { email, password, redirect: false });
    if (res?.error) {
      setError("Invalid email or password. Please try again.");
      setLoading(null);
      return;
    }
    // Full navigation so the new session is read and root routes by role.
    window.location.href = "/";
  }

  function onSso() {
    if (ENTRA_ENABLED) {
      signIn("microsoft-entra-id", { callbackUrl: "/" });
    } else {
      setError(
        "Single sign-on isn't configured in this environment. Continue with your email, or use a demo account below.",
      );
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4 py-10">
      {/* Brand */}
      <div className="mb-7 flex items-center gap-2.5">
        <LogoTile className="h-10 w-10" />
        <div>
          <div className="text-body-lg font-semibold leading-none text-on-surface">Auxilab</div>
          <div className="mt-0.5 font-mono text-label-sm uppercase tracking-wider text-on-surface-variant">
            Expense Management
          </div>
        </div>
      </div>

      {/* Auth card */}
      <main className="w-full max-w-[400px] rounded-xl border border-outline-variant bg-surface-container-lowest p-8 shadow-[0_1px_3px_rgba(16,24,40,0.08)]">
        <h1 className="text-headline-md font-semibold text-on-surface">Sign in</h1>
        <p className="mt-1 text-body-sm text-on-surface-variant">
          Use your work account to continue.
        </p>

        {error && (
          <div
            role="alert"
            className="mt-5 flex items-start gap-2 rounded-md border border-error/20 bg-error-container px-3 py-2.5 text-body-sm text-on-error-container"
          >
            <Icon name="error" className="mt-0.5 shrink-0 text-[18px]" />
            <span>{error}</span>
          </div>
        )}

        {/* SSO first — enterprise pattern */}
        <Button
          variant="outline"
          className="mt-6 w-full"
          disabled={loading !== null}
          onClick={onSso}
        >
          <Icon name="window" /> Continue with Microsoft Entra ID
        </Button>

        <div className="my-5 flex items-center gap-3">
          <span className="h-px flex-1 bg-outline-variant" />
          <span className="text-label-md text-on-surface-variant">or</span>
          <span className="h-px flex-1 bg-outline-variant" />
        </div>

        <form
          onSubmit={handleSubmit((v) => doLogin(v.email, v.password, "form"))}
          className="space-y-4"
        >
          <div className="space-y-1.5">
            <label htmlFor="email" className="block text-body-sm font-medium text-on-surface">
              Work email
            </label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              placeholder="you@company.com"
              aria-invalid={!!errors.email}
              {...register("email")}
            />
            {errors.email && <p className="text-label-md text-error">{errors.email.message}</p>}
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label htmlFor="password" className="block text-body-sm font-medium text-on-surface">
                Password
              </label>
              <a href="#" className="text-label-md font-medium text-secondary hover:underline">
                Forgot password?
              </a>
            </div>
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                placeholder="••••••••"
                className="pr-10"
                aria-invalid={!!errors.password}
                {...register("password")}
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-on-surface-variant transition-colors hover:text-on-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-secondary"
              >
                <Icon name={showPassword ? "visibility_off" : "visibility"} className="text-[18px]" />
              </button>
            </div>
            {errors.password && (
              <p className="text-label-md text-error">{errors.password.message}</p>
            )}
          </div>

          <label className="flex select-none items-center gap-2 text-body-sm text-on-surface-variant">
            <input
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
              className="h-4 w-4 rounded border-outline-variant text-secondary focus:ring-secondary"
            />
            Keep me signed in
          </label>

          <Button type="submit" className="w-full" disabled={loading !== null}>
            {loading === "form" ? "Signing in…" : "Sign in"}
          </Button>
        </form>

        {/* Trust indicator */}
        <div className="mt-6 flex items-center justify-center gap-1.5 text-label-md text-on-surface-variant">
          <Icon name="lock" className="text-[14px]" />
          Encrypted connection · SOC 2 Type II
        </div>
      </main>

      {/* Demo access — visually secondary, behind a disclosure */}
      <div className="mt-4 w-full max-w-[400px]">
        <button
          onClick={() => setShowDemo((v) => !v)}
          aria-expanded={showDemo}
          className="mx-auto flex items-center gap-1 rounded-md px-2 py-1 text-label-md text-on-surface-variant transition-colors hover:text-on-surface"
        >
          <Icon name="science" className="text-[14px]" /> Demo access
          <Icon name={showDemo ? "expand_less" : "expand_more"} className="text-[16px]" />
        </button>
        {showDemo && (
          <div className="mt-2 grid grid-cols-2 gap-2 rounded-lg border border-outline-variant bg-surface-container-low p-3">
            {DEMO_ACCOUNTS.map((d) => (
              <button
                key={d.email}
                type="button"
                disabled={loading !== null}
                onClick={() => doLogin(d.email, "demo", d.email)}
                className="flex items-center gap-2 rounded-md border border-outline-variant bg-surface-container-lowest px-3 py-2 text-left text-body-sm transition-colors hover:border-secondary hover:bg-surface-container-low disabled:opacity-50"
              >
                <Icon name={d.icon} className="text-[18px] text-secondary" />
                <span className="font-medium text-on-surface">
                  {loading === d.email ? "…" : d.label}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      <p className="mt-8 font-mono text-label-sm uppercase tracking-wider text-on-surface-variant">
        An Auxiliobits platform
      </p>
    </div>
  );
}
