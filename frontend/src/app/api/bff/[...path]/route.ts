/**
 * Backend-for-Frontend (BFF) proxy — resolves S-H2.
 *
 * The browser calls this same-origin route (`/api/bff/<backend-path>`) WITHOUT a token.
 * Here, server-side, we read the access token from the encrypted, HttpOnly Auth.js JWT
 * cookie (`getToken`) and attach it as `Authorization: Bearer` when forwarding to the
 * FastAPI backend. The token therefore never reaches client-side JavaScript and is never
 * exposed at `/api/auth/session`.
 *
 * RBAC/audit are unchanged: the backend still validates the same bearer token and enforces
 * every check. MCP and the public pre-auth endpoints (login/forgot-password) are unaffected.
 */
import { getToken } from "next-auth/jwt";
import { type NextRequest, NextResponse } from "next/server";

// Server-only backend origin — never shipped to the browser bundle.
const BACKEND = (
  process.env.BACKEND_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  ""
).replace(/\/$/, "");

export const runtime = "nodejs"; // getToken needs Node crypto, not the edge runtime
export const dynamic = "force-dynamic"; // never cache a proxied, per-user request

// Only these response headers are forwarded back to the browser (incl. file downloads).
const PASS_RESPONSE_HEADERS = ["content-type", "content-disposition", "cache-control"];

async function proxy(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;

  const secure = process.env.NODE_ENV === "production";
  const cookieName = secure ? "__Secure-authjs.session-token" : "authjs.session-token";
  const token = await getToken({
    req,
    secret: process.env.AUTH_SECRET,
    secureCookie: secure,
    salt: cookieName,
    cookieName,
  });
  const accessToken = (token as { accessToken?: string } | null)?.accessToken;

  const target = `${BACKEND}/${path.join("/")}${req.nextUrl.search}`;
  const headers = new Headers();
  const ct = req.headers.get("content-type");
  if (ct) headers.set("content-type", ct); // preserve multipart boundary on uploads
  const accept = req.headers.get("accept");
  if (accept) headers.set("accept", accept);
  if (accessToken) headers.set("authorization", `Bearer ${accessToken}`);

  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  const body = hasBody ? await req.arrayBuffer() : undefined;

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: req.method,
      headers,
      body,
      redirect: "manual",
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ detail: "Upstream service unavailable." }, { status: 502 });
  }

  const resHeaders = new Headers();
  for (const h of PASS_RESPONSE_HEADERS) {
    const v = upstream.headers.get(h);
    if (v) resHeaders.set(h, v);
  }
  return new NextResponse(upstream.body, { status: upstream.status, headers: resHeaders });
}

export {
  proxy as GET,
  proxy as POST,
  proxy as PUT,
  proxy as PATCH,
  proxy as DELETE,
};
