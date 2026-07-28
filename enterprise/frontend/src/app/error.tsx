"use client";

import { useEffect } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { LogoTile } from "@/components/logo";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Surface the error for observability; replace with your reporter as needed.
    console.error(error);
  }, [error]);

  return (
    <main className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-background px-6 py-16 text-center">
      {/* Ambient brand backdrop */}
      <div className="aurora noise pointer-events-none absolute inset-0 -z-10 opacity-[0.12]" />
      <div className="pointer-events-none absolute -right-24 -top-24 -z-10 h-72 w-72 rounded-full bg-error/5" />

      <div className="w-full max-w-md animate-slide-up">
        {/* Brand mark */}
        <div className="mb-10 flex items-center justify-center gap-3">
          <LogoTile className="h-11 w-11 shadow-xs" />
          <div className="text-left">
            <p className="text-headline-md font-bold leading-none text-primary">Auxilab</p>
            <p className="font-mono text-label-sm uppercase tracking-wider text-on-surface-variant">
              Expense Management
            </p>
          </div>
        </div>

        {/* Error glyph */}
        <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full border border-error/20 bg-error-container">
          <Icon name="error" className="text-[32px] text-error" />
        </div>

        <p className="font-mono text-label-md uppercase tracking-wider text-error">
          Something went wrong
        </p>
        <h1 className="mt-3 text-headline-xl font-bold leading-tight text-on-surface">
          We hit an unexpected error
        </h1>
        <p className="mt-4 text-body-lg text-on-surface-variant">
          Sorry about that. The issue has been logged. You can try again, or head back
          home and pick up where you left off.
        </p>

        {error.digest && (
          <p className="mt-4 inline-block rounded border border-outline-variant bg-surface-container-low px-3 py-1.5 font-mono text-label-sm uppercase tracking-wider text-on-surface-variant">
            Reference: {error.digest}
          </p>
        )}

        <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Button size="lg" className="w-full sm:w-auto" onClick={() => reset()}>
            <Icon name="refresh" /> Try again
          </Button>
          <Button asChild variant="outline" size="lg" className="w-full sm:w-auto">
            <Link href="/">
              <Icon name="home" /> Back to home
            </Link>
          </Button>
        </div>
      </div>

      <p className="absolute bottom-6 font-mono text-label-sm uppercase tracking-wider text-on-surface-variant/70">
        An Auxiliobits finance-automation platform
      </p>
    </main>
  );
}
