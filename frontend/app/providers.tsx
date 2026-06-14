"use client";

// REFERENCE SCAFFOLD ONLY — see README.md.
// Client provider tree: TanStack Query (SCOPING §10). NextAuth's SessionProvider
// would also mount here in a real app; omitted from the stub to avoid pulling the
// full auth runtime into the reference scaffold.

import { useState, type ReactNode } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { makeQueryClient } from "@/lib/query-client";

export function Providers({ children }: { children: ReactNode }) {
  // One client per browser session (lazy-init so it's not shared across requests).
  const [queryClient] = useState(() => makeQueryClient());

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}
