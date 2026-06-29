"use client";

import { useSession } from "next-auth/react";
import type { Role } from "@/data/types";

/**
 * The signed-in user's role, read from the NextAuth session (Entra/credentials).
 * Drives the role switcher's access hierarchy — an admin keeps full access while
 * viewing lower portals. Falls back to `employee` (least privilege) while the
 * session is loading or absent.
 */
export function useSessionRole(): {
  sessionRole: Role;
  status: "authenticated" | "loading" | "unauthenticated";
} {
  const { data, status } = useSession();
  return {
    sessionRole: (data?.user?.role ?? "employee") as Role,
    status,
  };
}
