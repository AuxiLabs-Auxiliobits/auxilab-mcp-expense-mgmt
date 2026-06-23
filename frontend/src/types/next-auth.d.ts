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
    accessToken?: string;
    user: { role?: Role; agencyId?: string; agencyName?: string } & DefaultSession["user"];
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
