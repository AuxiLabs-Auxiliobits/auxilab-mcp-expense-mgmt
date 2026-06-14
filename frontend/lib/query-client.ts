// REFERENCE SCAFFOLD ONLY — see README.md.
// TanStack Query client factory (SCOPING §10 — server-state management).
// The provider that mounts this lives in app/providers.tsx ('use client').

import { QueryClient } from "@tanstack/react-query";

export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        retry: 1,
      },
    },
  });
}

// Centralized query keys so cache invalidation is consistent across the app.
export const queryKeys = {
  sheets: ["sheets"] as const,
  sheet: (sheetId: string) => ["sheet", sheetId] as const,
  managerQueue: (agencyId: string) => ["manager-queue", agencyId] as const,
  financeQueue: ["finance-queue"] as const,
  auditLog: ["audit-log"] as const,
};
