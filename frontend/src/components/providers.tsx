"use client";

import { useState } from "react";
import {
  QueryCache,
  QueryClient,
  QueryClientProvider,
  MutationCache,
} from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { Toaster } from "sonner";
import { ThemeProvider, useTheme } from "next-themes";
import { SessionProvider, signOut } from "next-auth/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ReceiptUploadsProvider } from "@/data/receipt-uploads";
import { isUnauthorized } from "@/data/http";

// A backend 401 means the NextAuth cookie has outlived the access token (a
// "stale session"). Tear the session down and route to /login. Guarded so a
// burst of parallel 401s triggers a single sign-out rather than a redirect loop.
let signingOut = false;
function handleSessionExpiry(error: unknown) {
  if (!isUnauthorized(error) || signingOut) return;
  signingOut = true;
  signOut({ redirectTo: "/login" });
}

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

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        queryCache: new QueryCache({ onError: handleSessionExpiry }),
        mutationCache: new MutationCache({ onError: handleSessionExpiry }),
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            refetchOnWindowFocus: false,
            // Never burn a retry on an auth failure — it can't succeed.
            retry: (count, error) => !isUnauthorized(error) && count < 1,
          },
        },
      }),
  );

  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="light"
      themes={["light", "dark", "high-contrast"]}
      enableSystem
      disableTransitionOnChange
    >
      <SessionProvider>
        <QueryClientProvider client={queryClient}>
          <ReceiptUploadsProvider>
            <TooltipProvider delayDuration={200}>{children}</TooltipProvider>
          </ReceiptUploadsProvider>
          <ThemedToaster />
          {process.env.NODE_ENV === "development" && (
            <ReactQueryDevtools initialIsOpen={false} buttonPosition="bottom-left" />
          )}
        </QueryClientProvider>
      </SessionProvider>
    </ThemeProvider>
  );
}
