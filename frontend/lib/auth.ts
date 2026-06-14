// REFERENCE SCAFFOLD ONLY — see README.md.
// NextAuth / Auth.js (v5) config wired to Microsoft Entra External ID (SCOPING §10, §13).
// Entra brokers Google/Microsoft/SSO and issues OIDC tokens carrying role + agency
// claims (SCOPING §2, §3). We surface those claims on the session so the UI can
// render role/agency-appropriate views. The backend independently validates the JWT.

import NextAuth, { type DefaultSession } from "next-auth";
import MicrosoftEntraID from "next-auth/providers/microsoft-entra-id";
import type { Role } from "@/types";

// Augment the session/JWT with our role + agency claims.
declare module "next-auth" {
  interface Session {
    user: {
      role: Role;
      agencyId: string;
      agencyName?: string;
      accessToken?: string;
    } & DefaultSession["user"];
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    role?: Role;
    agencyId?: string;
    agencyName?: string;
    accessToken?: string;
  }
}

// TODO(reference): claim names below ("roles", "agency_id") must match what the
// Entra External ID app registration emits. Map app roles → our Role union.
export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    MicrosoftEntraID({
      clientId: process.env.AZURE_AD_CLIENT_ID!,
      clientSecret: process.env.AZURE_AD_CLIENT_SECRET!,
      // For Entra External ID (CIAM) use the tenant/issuer authority.
      issuer:
        process.env.AZURE_AD_ISSUER ??
        `https://login.microsoftonline.com/${process.env.AZURE_AD_TENANT_ID}/v2.0`,
      authorization: { params: { scope: "openid profile email offline_access" } },
    }),
  ],
  callbacks: {
    // Lift role + agency claims off the ID/access token into the JWT.
    async jwt({ token, profile, account }) {
      if (account?.access_token) {
        token.accessToken = account.access_token;
      }
      if (profile) {
        // STUB: real claim extraction depends on Entra app-role / claims mapping.
        const claims = profile as Record<string, unknown>;
        const roles = claims["roles"] as string[] | undefined;
        token.role = (roles?.[0]?.toLowerCase() as Role) ?? token.role ?? "employee";
        token.agencyId = (claims["agency_id"] as string) ?? token.agencyId ?? "";
        token.agencyName = (claims["agency_name"] as string) ?? token.agencyName;
      }
      return token;
    },
    async session({ session, token }) {
      session.user.role = token.role ?? "employee";
      session.user.agencyId = token.agencyId ?? "";
      session.user.agencyName = token.agencyName;
      session.user.accessToken = token.accessToken;
      return session;
    },
  },
  pages: {
    signIn: "/login",
  },
});
