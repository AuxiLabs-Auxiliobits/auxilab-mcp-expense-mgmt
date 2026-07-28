import type { DefaultSession } from "next-auth";
import type { Role } from "@/data/types";

declare module "next-auth" {
  interface User {
    role?: Role;
    agencyId?: string;
    agencyName?: string;
    accessToken?: string;
  }
  interface Session {
    // Note: NO accessToken here by design (S-H2) — the token lives only on the JWT (below),
    // read server-side by the BFF proxy. The client session never carries the bearer token.
    error?: string;
    user: { role?: Role; agencyId?: string; agencyName?: string } & DefaultSession["user"];
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    role?: Role;
    agencyId?: string;
    agencyName?: string;
    accessToken?: string;
    // Federated (OIDC) session state for silent refresh + rotation.
    refreshToken?: string;
    expiresAt?: number; // epoch ms when accessToken expires
    provider?: string;
    error?: "RefreshFailed" | "IdentityResolutionFailed";
  }
}
