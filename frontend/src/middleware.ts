import NextAuth from "next-auth";
import { authConfig } from "@/auth.config";

// Edge middleware: runs the `authorized` callback (auth.config) on EVERY request
// except framework internals/static assets — protect-by-default. The callback
// allows the public allowlist and requires a valid session + role for the rest.
export const { auth: middleware } = NextAuth(authConfig);

export const config = {
  // Match all paths EXCEPT: next-auth API (/api/auth), Next internals, the favicon,
  // and any file with an extension (static assets in /public). Everything else —
  // including /employee, /super-admin, /dashboard, /reports, etc. — is guarded.
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|.*\\..*).*)"],
};

