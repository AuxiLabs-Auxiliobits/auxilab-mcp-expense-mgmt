import { redirect } from "next/navigation";
import { auth } from "@/auth";
import { PortalShell } from "@/components/layout/portal-shell";

/**
 * Server-side guard (defense-in-depth). Even if edge middleware is bypassed or
 * misconfigured, no portal page renders without a valid authenticated session —
 * the check runs on the server before any child UI is produced.
 */
export default async function PortalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();
  if (!session?.user?.role) redirect("/login");
  return <PortalShell>{children}</PortalShell>;
}
