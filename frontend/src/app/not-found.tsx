import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { LogoMark, LogoTile } from "@/components/logo";

export default function NotFound() {
  return (
    <main className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-background px-6 py-16 text-center">
      {/* Ambient brand backdrop */}
      <div className="aurora noise pointer-events-none absolute inset-0 -z-10 opacity-[0.12]" />
      <div className="pointer-events-none absolute -right-24 -top-24 -z-10 h-72 w-72 rounded-full bg-primary/5" />
      <div className="pointer-events-none absolute -bottom-28 -left-16 -z-10 text-on-surface opacity-[0.04]">
        <LogoMark className="h-80 w-80" />
      </div>

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

        <p className="font-mono text-label-md uppercase tracking-wider text-secondary">
          Error 404
        </p>
        <h1 className="mt-3 text-headline-xl font-bold leading-tight text-on-surface">
          Page not found
        </h1>
        <p className="mt-4 text-body-lg text-on-surface-variant">
          The page you&apos;re looking for doesn&apos;t exist, may have moved, or you may
          not have access to it. Let&apos;s get you back to familiar ground.
        </p>

        <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Button asChild size="lg" className="w-full sm:w-auto">
            <Link href="/">
              <Icon name="home" /> Back to home
            </Link>
          </Button>
          <Button asChild variant="outline" size="lg" className="w-full sm:w-auto">
            <Link href="/login">
              <Icon name="login" /> Sign in
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
