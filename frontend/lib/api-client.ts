// REFERENCE SCAFFOLD ONLY — see README.md.
// Typed fetch wrapper to the FastAPI backend (NEXT_PUBLIC_API_BASE_URL, SCOPING §2/§11).
// Attaches the bearer token from the NextAuth session so the backend can enforce
// RBAC + agency scope server-side (SCOPING §3.3 — the server is authoritative).

import type { ExpenseSheet } from "@/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public body?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  // Bearer token from the session (lib/auth.ts). Passed explicitly so this module
  // stays usable from both server components and client components.
  token?: string;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { body, token, headers, ...rest } = opts;

  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    let parsed: unknown;
    try {
      parsed = await res.json();
    } catch {
      parsed = await res.text();
    }
    throw new ApiError(res.status, `API ${res.status} on ${path}`, parsed);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// ---- Stubbed endpoint surface ----
// TODO(reference): these mirror the FastAPI routes (SCOPING §11). All access control
// and agency scoping is enforced on the server; the paths here are illustrative.
export const apiClient = {
  get: <T>(path: string, token?: string) =>
    request<T>(path, { method: "GET", token }),
  post: <T>(path: string, body: unknown, token?: string) =>
    request<T>(path, { method: "POST", body, token }),
  patch: <T>(path: string, body: unknown, token?: string) =>
    request<T>(path, { method: "PATCH", body, token }),

  // Convenience typed helpers (stubs)
  sheets: {
    list: (token?: string) => request<ExpenseSheet[]>("/sheets", { token }),
    get: (sheetId: string, token?: string) =>
      request<ExpenseSheet>(`/sheets/${sheetId}`, { token }),
  },
};

export { API_BASE_URL };
