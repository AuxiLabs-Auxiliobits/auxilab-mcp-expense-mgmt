import NextAuth from "next-auth";
import { authConfig } from "@/auth.config";

// Edge middleware: protects the portal routes and enforces hierarchical,
// role-based access via the `authorized` callback in auth.config.
export const { auth: middleware } = NextAuth(authConfig);

export const config = {
  matcher: [
    "/employee/:path*",
    "/manager/:path*",
    "/finance/:path*",
    "/admin/:path*",
  ],
};

