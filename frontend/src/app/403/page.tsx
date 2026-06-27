import type { Metadata } from "next";
import Link from "next/link";
import { auth } from "@/auth";
import { PORTAL_BASE } from "@/lib/rbac";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";

export const metadata: Metadata = { title: "Access Denied" };

/**
 * 403 Access Denied — shown (via middleware rewrite) to an authenticated user who
 * lacks access to the requested route. We do NOT bounce them to another dashboard;
 * the attempted URL stays in the address bar.
 */
export default async function ForbiddenPage() {
  const session = await auth();
  const home = session?.user?.role ? PORTAL_BASE[session.user.role] : "/login";

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-background px-4 text-center">
      <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-error/15 text-error">
        <Icon name="lock" className="text-[30px]" />
      </span>
      <div className="text-headline-xl font-bold text-on-surface">403</div>
      <h1 className="text-headline-lg font-semibold text-on-surface">Access denied</h1>
      <p className="max-w-md text-body-sm text-on-surface-variant">
        You don&apos;t have permission to view this page. If you believe this is a mistake,
        contact your administrator.
      </p>
      <Button asChild className="mt-2">
        <Link href={home}>
          <Icon name="arrow_back" /> Back to your dashboard
        </Link>
      </Button>
    </div>
  );
}
