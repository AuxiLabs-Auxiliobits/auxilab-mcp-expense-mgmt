"use client";

import { LogoTile } from "@/components/logo";
import { AuthThemeToggle } from "./auth-theme-toggle";

/** Centered, themed glass card scaffold shared by the forgot/reset-password screens —
 * same visual language as the login experience (aurora backdrop, gradient-edge card). */
export function AuthCardShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative flex min-h-screen w-full items-center justify-center overflow-hidden bg-background p-4 py-10">
      <div aria-hidden className="aurora pointer-events-none absolute inset-0 -z-10 opacity-60" />
      <div className="absolute right-4 top-4 z-30 animate-fade-in sm:right-6 sm:top-6">
        <AuthThemeToggle />
      </div>

      <div className="w-full max-w-[420px] animate-scale-in">
        <div className="mb-6 flex items-center justify-center gap-2.5">
          <LogoTile className="h-9 w-9" />
          <div>
            <div className="text-body-lg font-semibold leading-none text-on-surface">Auxilab</div>
            <div className="mt-0.5 text-label-sm uppercase tracking-wider text-on-surface-variant">
              Expense Management
            </div>
          </div>
        </div>

        <div className="gradient-border rounded-3xl border border-outline-variant/40 bg-surface-container-lowest/70 p-6 shadow-elevation-3 backdrop-blur-2xl sm:p-8">
          {children}
        </div>

        <p className="mt-8 text-center text-label-sm uppercase tracking-wider text-on-surface-variant">
          An Auxiliobits platform
        </p>
      </div>
    </div>
  );
}

export function BackToSignIn() {
  return (
    <a
      href="/login"
      className="mt-6 flex items-center justify-center gap-1 text-label-md font-medium text-secondary hover:underline"
    >
      <span className="material-symbols-outlined text-[16px]">arrow_back</span> Back to sign in
    </a>
  );
}
