import NextAuth from "next-auth";
import MicrosoftEntraID from "next-auth/providers/microsoft-entra-id";
import Keycloak from "next-auth/providers/keycloak";
import Credentials from "next-auth/providers/credentials";
import { authConfig } from "@/auth.config";
import { usersByRole } from "@/data/mock";
import type { Role } from "@/data/types";

/**
 * Auth.js (NextAuth v5).
 *
 * Primary path: the **Credentials provider** posts {email, password} to your
 * existing backend login API (set `AUTH_LOGIN_URL`). The returned role + agency
 * are placed on the session and drive RBAC everywhere (UI + middleware).
 *
 * Secondary path: Microsoft Entra External ID SSO (set the AUTH_MICROSOFT_* env).
 *
 * Offline path: with no `AUTH_LOGIN_URL`, four demo accounts (one per role) let
 * the portal run without the backend — handy for review.
 */

// Demo accounts (used only when AUTH_LOGIN_URL is not configured).
const DEMO_BY_EMAIL: Record<string, Role> = {
  [usersByRole.employee.email.toLowerCase()]: "employee",
  [usersByRole.manager.email.toLowerCase()]: "manager",
  [usersByRole.finance.email.toLowerCase()]: "finance",
  [usersByRole.admin.email.toLowerCase()]: "admin",
};

const entraConfigured =
  !!process.env.AUTH_MICROSOFT_ENTRA_ID_ID &&
  !!process.env.AUTH_MICROSOFT_ENTRA_ID_ISSUER;

// Keycloak is our locally-runnable OIDC stand-in (identical Auth-Code + PKCE + refresh
// flow to Entra) — enabled only when configured, so it never breaks the default build.
const keycloakConfigured =
  !!process.env.AUTH_KEYCLOAK_ID && !!process.env.AUTH_KEYCLOAK_ISSUER;

export const { handlers, auth, signIn, signOut } = NextAuth({
  ...authConfig,
  providers: [
    // Only register Entra when configured — an empty issuer/clientId would
    // otherwise break every NextAuth endpoint (InvalidEndpoints).
    ...(entraConfigured
      ? [
          MicrosoftEntraID({
            clientId: process.env.AUTH_MICROSOFT_ENTRA_ID_ID,
            clientSecret: process.env.AUTH_MICROSOFT_ENTRA_ID_SECRET,
            issuer: process.env.AUTH_MICROSOFT_ENTRA_ID_ISSUER,
            // offline_access → refresh token (silent renewal); PKCE is on by default.
            // prompt=login forces re-authentication every time, so signing out and back
            // in always asks for credentials (Entra won't silently reuse its SSO session).
            authorization: {
              params: { scope: "openid profile email offline_access", prompt: "login" },
            },
          }),
        ]
      : []),
    ...(keycloakConfigured
      ? [
          Keycloak({
            clientId: process.env.AUTH_KEYCLOAK_ID!,
            clientSecret: process.env.AUTH_KEYCLOAK_SECRET,
            issuer: process.env.AUTH_KEYCLOAK_ISSUER!,
            authorization: { params: { scope: "openid profile email offline_access" } },
          }),
        ]
      : []),
    Credentials({
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      authorize: async (credentials) => {
        const email = String(credentials?.email ?? "").trim().toLowerCase();
        const password = String(credentials?.password ?? "");
        if (!email || !password) return null;

        const loginUrl = process.env.AUTH_LOGIN_URL;

        // ── Real backend login (Expense Management API) ─────────────────────
        // POST /auth/login → { access_token }; profile from GET /auth/me.
        if (loginUrl) {
          try {
            const res = await fetch(loginUrl, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ email, password }),
            });
            if (!res.ok) return null;
            const token: string | undefined = (await res.json())?.access_token;
            if (!token) return null;

            const base = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
            let role: Role = "employee";
            let agencyId = "";
            let agencyName = "";
            let name = email;
            let id = email;
            try {
              const meRes = await fetch(`${base}/auth/me`, {
                headers: { Authorization: `Bearer ${token}` },
              });
              if (meRes.ok) {
                const me = await meRes.json();
                role = String(me.role ?? "employee").toLowerCase() as Role;
                agencyId = me.agency_id ?? me.agencyId ?? "";
                agencyName = me.agency_name ?? me.agencyName ?? "";
                name = me.name ?? me.full_name ?? me.email ?? email;
                id = String(me.subject_id ?? me.id ?? email);
              }
            } catch {
              /* keep defaults if /auth/me is unavailable */
            }
            return { id, name, email, role, agencyId, agencyName, accessToken: token };
          } catch {
            return null;
          }
        }

        // ── Demo fallback (no AUTH_LOGIN_URL) ───────────────────────────────
        const role = DEMO_BY_EMAIL[email];
        if (!role) return null;
        const u = usersByRole[role];
        return {
          id: u.id,
          name: u.name,
          email: u.email,
          role,
          agencyId: u.agencyId,
          agencyName: u.agencyName ?? "Crispin",
        };
      },
    }),
  ],
});
