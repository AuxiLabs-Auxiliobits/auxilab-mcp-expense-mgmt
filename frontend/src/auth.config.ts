import type { NextAuthConfig } from "next-auth";
import type { JWT } from "next-auth/jwt";
import { NextResponse } from "next/server";
import type { Role } from "@/data/types";
import { ROLE_VIEW_ACCESS } from "@/lib/rbac";

/**
 * Edge-safe auth config shared by the middleware and the full server config.
 * Holds the token/session shaping and the route-authorization rules so RBAC is
 * enforced at the edge (defense-in-depth, SCOPING.md §3.3) — not just in the UI.
 * Providers (which run Node-only logic) are added in `auth.ts`.
 */

// Protect-by-DEFAULT: every route requires auth EXCEPT this explicit allowlist.
// Adding a new section can never accidentally expose it.
const PUBLIC_PATHS = new Set<string>([
  "/",
  "/login",
  "/forgot-password",
  "/reset-password",
  "/privacy",
  "/terms",
]);

function isPublic(path: string): boolean {
  return PUBLIC_PATHS.has(path);
}

function targetPortal(path: string): Role {
  if (path.startsWith("/manager")) return "manager";
  if (path.startsWith("/finance")) return "finance";
  if (path.startsWith("/admin") || path.startsWith("/super-admin")) return "admin";
  return "employee";
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const REFRESH_SKEW_MS = 60_000; // refresh 1 min before expiry

/**
 * Federated identity resolution (DB-by-email JIT): after an OIDC sign-in we hold the IdP's
 * token, but role + agency live in OUR database. Calling the backend `/auth/me` with the IdP
 * token triggers the backend's OidcAuthProvider → JIT link → returns the resolved identity.
 */
async function hydrateAppIdentity(token: JWT): Promise<void> {
  try {
    const res = await fetch(`${API_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${token.accessToken}` },
    });
    if (!res.ok) {
      token.error = "IdentityResolutionFailed";
      return;
    }
    const me = await res.json();
    token.role = String(me.role ?? "employee").toLowerCase() as Role;
    token.agencyId = me.agency_id ?? me.agencyId ?? "";
    token.agencyName = me.agency_name ?? me.agencyName ?? "";
    token.name = me.name ?? token.name;
    delete token.error;
  } catch {
    token.error = "IdentityResolutionFailed";
  }
}

/**
 * Silent refresh with rotation: exchange the refresh token for a fresh access token at the
 * IdP token endpoint. On failure the token is flagged so the session ends and the user
 * re-authenticates. Token URL + client creds are env-configured (provider-agnostic).
 */
async function refreshAccessToken(token: JWT): Promise<void> {
  const tokenUrl = process.env.AUTH_OIDC_TOKEN_URL;
  const clientId = process.env.AUTH_OIDC_CLIENT_ID;
  const clientSecret = process.env.AUTH_OIDC_CLIENT_SECRET;
  if (!tokenUrl || !clientId || !token.refreshToken) {
    token.error = "RefreshFailed";
    return;
  }
  try {
    const body = new URLSearchParams({
      grant_type: "refresh_token",
      refresh_token: token.refreshToken,
      client_id: clientId,
      ...(clientSecret ? { client_secret: clientSecret } : {}),
    });
    const res = await fetch(tokenUrl, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
    if (!res.ok) {
      token.error = "RefreshFailed";
      return;
    }
    const refreshed = await res.json();
    // Keep forwarding the ID token (audience = our client id) to the backend, not the
    // Graph-scoped access token. A refresh with openid scope re-issues the id_token.
    token.accessToken = refreshed.id_token ?? refreshed.access_token;
    token.expiresAt = Date.now() + (refreshed.expires_in ?? 300) * 1000;
    // Refresh-token rotation: keep the new one if the IdP issued it.
    if (refreshed.refresh_token) token.refreshToken = refreshed.refresh_token;
    delete token.error;
  } catch {
    token.error = "RefreshFailed";
  }
}

export const authConfig = {
  trustHost: true,
  pages: { signIn: "/login" },
  // No clock-based cap on an active session: the cookie lives long and is rolled
  // forward on activity, so an active user is never logged out. Inactivity is enforced
  // separately by the client SessionManager (10-minute idle timeout). updateAge keeps
  // the JWT (and the refreshed access token) re-issued frequently while in use.
  session: { strategy: "jwt", maxAge: 30 * 24 * 60 * 60, updateAge: 5 * 60 },
  providers: [],
  callbacks: {
    async jwt({ token, user, account }) {
      // 1) Federated (OIDC: Entra / Keycloak / …) sign-in — the account carries the IdP
      //    tokens. Capture them, then resolve OUR role/agency from the backend (DB-by-email).
      //    NOTE: must be checked BEFORE the generic `user` branch — the Credentials provider
      //    also supplies an `account` (provider "credentials"), but with no access_token.
      if (account?.access_token) {
        // Our backend validates the bearer token's audience against OUR client id. With OIDC
        // scopes the access_token is minted for Microsoft Graph (wrong audience), whereas the
        // ID token's audience IS our client id — so forward the ID token to the backend.
        token.accessToken = account.id_token ?? account.access_token;
        token.refreshToken = account.refresh_token;
        token.expiresAt = account.expires_at ? account.expires_at * 1000 : undefined;
        token.provider = account.provider;
        await hydrateAppIdentity(token);
        return token;
      }

      // 2) Local credentials sign-in (initial) — the authorize() result carries role/agency.
      if (user) {
        token.role = user.role;
        token.agencyId = user.agencyId;
        token.agencyName = user.agencyName;
        token.accessToken = user.accessToken;
        return token;
      }

      // 3) Subsequent requests — silently refresh the IdP access token before it expires.
      if (token.expiresAt && Date.now() > token.expiresAt - REFRESH_SKEW_MS && token.refreshToken) {
        await refreshAccessToken(token);
      }
      return token;
    },
    session({ session, token }) {
      if (token.role) session.user.role = token.role as Role;
      if (token.agencyId) session.user.agencyId = token.agencyId as string;
      if (token.agencyName) session.user.agencyName = token.agencyName as string;
      if (token.accessToken) session.accessToken = token.accessToken as string;
      // Surface refresh/identity failures so the client can force a clean re-login.
      if (token.error) session.error = token.error;
      return session;
    },
    authorized({ auth, request: { nextUrl } }) {
      const path = nextUrl.pathname;

      // 1) Public routes are always allowed.
      if (isPublic(path)) return true;

      // 2) Everything else REQUIRES authentication. No session → /login (signIn page).
      const role = auth?.user?.role as Role | undefined;
      if (!role) return false;

      // 3) Role gate for the portal segments. Authenticated-but-unauthorized → 403
      //    (rewrite keeps the attempted URL; we never bounce them to another dashboard).
      const isPortal = /^\/(employee|manager|finance|admin|super-admin)(\/|$)/.test(path);
      if (isPortal && !ROLE_VIEW_ACCESS[role].includes(targetPortal(path))) {
        return NextResponse.rewrite(new URL("/403", nextUrl));
      }

      // 4) Authenticated; any other protected route (settings, reports, …) is allowed.
      return true;
    },
  },
} satisfies NextAuthConfig;
