import { redirect } from "next/navigation";
import { auth } from "@/auth";
import { PORTAL_BASE } from "@/lib/rbac";

/**
 * Server guard for the /login segment: an already-authenticated user who lands
 * on /login is sent straight to their portal instead of seeing the sign-in
 * form (which read as being "logged out"). The session is never cleared.
 */
export default async function LoginLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();
  if (session?.user?.role) {
    redirect(PORTAL_BASE[session.user.role]);
  }
  return <>{children}</>;
}
