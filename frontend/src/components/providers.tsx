"use client";

import { useState } from "react";
import {
  QueryCache,
  QueryClient,
  QueryClientProvider,
  MutationCache,
} from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { toast } from "sonner";
import { Toaster } from "sonner";
import { ThemeProvider, useTheme } from "next-themes";
import { SessionProvider } from "next-auth/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { GlobalProgress } from "@/components/layout/global-progress";
import { ApiError } from "@/data/http";
import { triggerSessionExpired } from "@/lib/session";

function ThemedToaster() {
  const { resolvedTheme } = useTheme();
  return (
    <Toaster
      position="top-right"
      richColors
      closeButton
      theme={resolvedTheme === "dark" ? "dark" : "light"}
    />
  );
}

/** Turn any thrown error into a single user-friendly string for a toast. */
function messageFor(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error && error.message) return error.message;
  return "Something went wrong. Please try again.";
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        // Global error surfacing: every failed query/mutation shows a toast and
        // React Query automatically clears isLoading/isPending, so loaders never
        // get stuck after a failure. Aborted/cancelled requests are ignored.
        queryCache: new QueryCache({
          onError: (error) => {
            if (error instanceof ApiError && error.kind === "aborted") return;
            // 401 = expired/revoked session → auto logout (handled by SessionManager).
            if (error instanceof ApiError && error.status === 401) {
              triggerSessionExpired("expired");
              return;
            }
            toast.error(messageFor(error));
          },
        }),
        mutationCache: new MutationCache({
          onError: (error, _vars, _ctx, mutation) => {
            if (error instanceof ApiError && error.kind === "aborted") return;
            if (error instanceof ApiError && error.status === 401) {
              triggerSessionExpired("expired");
              return;
            }
            // Opt-out for hooks whose call sites already show a tailored error (e.g. flows
            // that also do non-mutation work like receipt uploads in the same try/catch).
            if (mutation.options.meta?.suppressErrorToast) return;
            toast.error(messageFor(error));
          },
        }),
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            refetchOnWindowFocus: false,
            // Don't retry client errors (4xx) — only transient network/5xx, once.
            retry: (count, error) => {
              if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
                return false;
              }
              return count < 1;
            },
          },
        },
      }),
  );

  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="light"
      themes={["light", "dark"]}
      enableSystem
      disableTransitionOnChange
    >
      {/* Refetch the session on a 5-minute interval so the access token is refreshed before it
          expires — an active user's API calls never 401. We deliberately do NOT refetch on every
          window focus: that fired a /api/auth/session request on each tab switch, and any transient
          failure surfaced as a noisy next-auth ClientFetchError. The interval keeps the token fresh
          on its own. `refetchWhenOffline={false}` avoids guaranteed-failing fetches while offline. */}
      <SessionProvider refetchInterval={5 * 60} refetchOnWindowFocus={false} refetchWhenOffline={false}>
        <QueryClientProvider client={queryClient}>
          <GlobalProgress />
          <TooltipProvider delayDuration={200}>{children}</TooltipProvider>
          <ThemedToaster />
          {process.env.NODE_ENV === "development" && (
            <ReactQueryDevtools initialIsOpen={false} buttonPosition="bottom-left" />
          )}
        </QueryClientProvider>
      </SessionProvider>
    </ThemeProvider>
  );
}
