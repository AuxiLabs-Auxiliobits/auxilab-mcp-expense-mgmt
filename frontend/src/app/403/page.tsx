import type { Metadata } from "next";
import { headers } from "next/headers";
import Link from "next/link";
import { auth } from "@/auth";
import { PORTAL_BASE } from "@/lib/rbac";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";

export const metadata: Metadata = { title: "403 Forbidden" };

/**
 * 403 Forbidden — shown (via middleware rewrite) when an authenticated user
 * requests a portal they are not authorised for. The attempted URL stays in
 * the address bar (middleware rewrite, not redirect) so the user can see
 * exactly which path was blocked.
 */
export default async function ForbiddenPage() {
  const session = await auth();
  const role = (session?.user?.role as string | undefined) ?? "unknown";
  const home = session?.user?.role ? PORTAL_BASE[session.user.role] : "/login";

  // Read the attempted path from the referer header (best-effort; may be absent).
  const headersList = await headers();
  const attempted = headersList.get("x-middleware-rewrite") ?? headersList.get("referer") ?? null;

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background px-4 text-center">
      {/* Status badge */}
      <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-error/15 text-error">
        <Icon name="lock" className="text-[34px]" />
      </span>

      {/* HTTP status */}
      <div className="font-mono text-[56px] font-bold leading-none tracking-tight text-error">
        403
      </div>

      <div className="space-y-1">
        <h1 className="text-headline-lg font-semibold text-on-surface">Forbidden</h1>
        <p className="font-mono text-label-md text-on-surface-variant">
          HTTP 403 — Insufficient role privileges
        </p>
      </div>

      {/* Detail card */}
      <div className="mt-2 w-full max-w-sm rounded-xl border border-outline-variant bg-surface-container-low px-5 py-4 text-left font-mono text-label-sm">
        <div className="flex items-center justify-between py-1">
          <span className="text-on-surface-variant">Your role</span>
          <span className="font-semibold capitalize text-on-surface">{role}</span>
        </div>
        <div className="border-t border-outline-variant" />
        <div className="flex items-center justify-between py-1">
          <span className="text-on-surface-variant">Required role</span>
          <span className="font-semibold text-error">higher privilege</span>
        </div>
        {attempted && (
          <>
            <div className="border-t border-outline-variant" />
            <div className="flex items-start justify-between gap-3 py-1">
              <span className="shrink-0 text-on-surface-variant">Attempted path</span>
              <span className="break-all text-right text-on-surface">{attempted}</span>
            </div>
          </>
        )}
      </div>

      <p className="max-w-sm text-body-sm text-on-surface-variant">
        Your account does not have access to this section. Each role is scoped to its own
        portal — contact your administrator if you need elevated access.
      </p>

      <Button asChild className="mt-1">
        <Link href={home}>
          <Icon name="arrow_back" /> Back to my dashboard
        </Link>
      </Button>
    </div>
  );
}
