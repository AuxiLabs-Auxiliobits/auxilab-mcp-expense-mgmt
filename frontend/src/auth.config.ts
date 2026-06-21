import type { NextAuthConfig } from "next-auth";
import type { Role } from "@/data/types";
import { PORTAL_BASE, ROLE_VIEW_ACCESS } from "@/lib/rbac";

/**
 * Edge-safe auth config shared by the middleware and the full server config.
 * Holds the token/session shaping and the route-authorization rules so RBAC is
 * enforced at the edge (defense-in-depth, SCOPING.md §3.3) — not just in the UI.
 * Providers (which run Node-only logic) are added in `auth.ts`.
 */
function targetPortal(path: string): Role {
  if (path.startsWith("/manager")) return "manager";
  if (path.startsWith("/finance")) return "finance";
  if (path.startsWith("/admin")) return "admin";
  return "employee";
}

export const authConfig = {
  trustHost: true,
  pages: { signIn: "/login" },
  providers: [],
  callbacks: {
    jwt({ token, user }) {
      if (user) {
        token.role = user.role;
        token.agencyId = user.agencyId;
        token.accessToken = user.accessToken;
      }
      return token;
    },
    session({ session, token }) {
      if (token.role) session.user.role = token.role as Role;
      if (token.agencyId) session.user.agencyId = token.agencyId as string;
      if (token.accessToken) session.accessToken = token.accessToken as string;
      return session;
    },
    authorized({ auth, request: { nextUrl } }) {
      const path = nextUrl.pathname;
      const isPortal = /^\/(employee|manager|finance|admin)(\/|$)/.test(path);
      if (!isPortal) return true;

      const role = auth?.user?.role as Role | undefined;
      if (!role) return false; // unauthenticated → redirect to signIn (/login)

      // Hierarchical access: a role may view its own portal and every lower one.
      if (ROLE_VIEW_ACCESS[role].includes(targetPortal(path))) return true;

      // Authenticated but not permitted → send to the role's home portal.
      return Response.redirect(new URL(PORTAL_BASE[role], nextUrl));
    },
  },
} satisfies NextAuthConfig;
