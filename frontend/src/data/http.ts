/**
 * Thin HTTP client for the FastAPI backend.
 *
 * The mock store stays the default so the app runs offline. Set
 * `NEXT_PUBLIC_API_BASE_URL` and `NEXT_PUBLIC_USE_BACKEND=true` to route data
 * through the real API. Each `api.ts` function uses `backend(path, fallback)`:
 * when the backend is enabled it calls the endpoint, otherwise it resolves the
 * mock — so wiring is incremental and never breaks the demo.
 */
import { getSession } from "next-auth/react";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
export const USE_BACKEND =
  !!API_BASE && process.env.NEXT_PUBLIC_USE_BACKEND === "true";

async function authHeader(): Promise<Record<string, string>> {
  try {
    const session = await getSession();
    const token = session?.accessToken;
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch {
    return {};
  }
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json", ...(await authHeader()) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`${method} ${path} → ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

/** Multipart upload (e.g. policy documents) with the bearer token. */
export async function apiUpload<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { ...(await authHeader()) },
    body: form,
  });
  if (!res.ok) {
    throw new Error(`POST ${path} → ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

/** Fetch binary content (e.g. a receipt) with the bearer token, as a Blob. */
export async function apiBlob(path: string): Promise<Blob> {
  const res = await fetch(`${API_BASE}${path}`, { headers: { ...(await authHeader()) } });
  if (!res.ok) {
    throw new Error(`GET ${path} → ${res.status} ${res.statusText}`);
  }
  return res.blob();
}

export const apiGet = <T>(path: string) => request<T>("GET", path);
export const apiPost = <T>(path: string, body?: unknown) => request<T>("POST", path, body);
export const apiPatch = <T>(path: string, body?: unknown) => request<T>("PATCH", path, body);
export const apiDelete = <T>(path: string) => request<T>("DELETE", path);

/** Use the backend when enabled, otherwise the provided mock fallback. */
export function backend<T>(call: () => Promise<T>, fallback: () => Promise<T>): Promise<T> {
  return USE_BACKEND ? call() : fallback();
}
