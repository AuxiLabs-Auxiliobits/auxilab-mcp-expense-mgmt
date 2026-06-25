/**
 * Thin HTTP client for the FastAPI backend.
 *
 * The mock store stays the default so the app runs offline. Set
 * `NEXT_PUBLIC_API_BASE_URL` and `NEXT_PUBLIC_USE_BACKEND=true` to route data
 * through the real API. Each `api.ts` function uses `backend(path, fallback)`:
 * when the backend is enabled it calls the endpoint, otherwise it resolves the
 * mock — so wiring is incremental and never breaks the demo.
 *
 * Every request goes through a single `request()` path that adds:
 *   • a hard timeout (so loaders never hang forever),
 *   • abort/cancellation support (React Query passes a signal),
 *   • a typed `ApiError` with a user-friendly message + HTTP status,
 * which the global QueryClient error handler turns into a toast.
 */
import { getSession } from "next-auth/react";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
export const USE_BACKEND =
  !!API_BASE && process.env.NEXT_PUBLIC_USE_BACKEND === "true";

/** Default per-request timeout. Long enough for cold starts, short enough to fail fast. */
export const REQUEST_TIMEOUT_MS = 30_000;

/** Typed error carrying the HTTP status + a message safe to show the user. */
export class ApiError extends Error {
  status: number;
  /** "timeout" | "network" | "http" | "aborted" */
  kind: "timeout" | "network" | "http" | "aborted";
  constructor(message: string, status: number, kind: ApiError["kind"]) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.kind = kind;
  }
}

function friendlyMessage(status: number, serverDetail?: string): string {
  if (status === 0) return "Network error — please check your connection and try again.";
  if (status === 401) return "Your session has expired. Please sign in again.";
  if (status === 403) return "You don't have permission to do that.";
  if (status === 404) return "We couldn't find what you were looking for.";
  if (status === 409) return serverDetail || "That action conflicts with the current state.";
  if (status === 413) return "That file is too large.";
  if (status === 422) return serverDetail || "Some of the submitted data is invalid.";
  if (status === 408) return "The request timed out. Please try again.";
  if (status >= 500) return "Something went wrong on our end. Please try again shortly.";
  return serverDetail || "Request failed. Please try again.";
}

/** Extract a human string from FastAPI's `{detail: ...}` (string | object | validation array). */
function extractDetail(body: unknown): string | undefined {
  if (!body || typeof body !== "object") return undefined;
  const detail = (body as Record<string, unknown>).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const first = detail[0] as Record<string, unknown> | undefined;
    if (first && typeof first.msg === "string") return first.msg;
  }
  if (detail && typeof detail === "object") {
    const err = (detail as Record<string, unknown>).error;
    if (typeof err === "string") return err;
  }
  return undefined;
}

async function authHeader(): Promise<Record<string, string>> {
  try {
    const session = await getSession();
    const token = session?.accessToken;
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch {
    return {};
  }
}

/**
 * Combine an external AbortSignal (from React Query) with an internal timeout so
 * the request is cancelled when EITHER fires. Returns the signal + a cleanup fn.
 */
function withTimeout(external?: AbortSignal): { signal: AbortSignal; done: () => void } {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(new DOMException("timeout", "TimeoutError")), REQUEST_TIMEOUT_MS);
  const onAbort = () => controller.abort((external as AbortSignal).reason);
  if (external) {
    if (external.aborted) controller.abort(external.reason);
    else external.addEventListener("abort", onAbort, { once: true });
  }
  return {
    signal: controller.signal,
    done: () => {
      clearTimeout(timer);
      external?.removeEventListener("abort", onAbort);
    },
  };
}

async function send<T>(
  method: string,
  path: string,
  body: unknown,
  isForm: boolean,
  signal?: AbortSignal,
): Promise<T> {
  const { signal: composed, done } = withTimeout(signal);
  try {
    const headers: Record<string, string> = { ...(await authHeader()) };
    let payload: BodyInit | undefined;
    if (isForm) {
      payload = body as FormData;
    } else if (body !== undefined) {
      headers["Content-Type"] = "application/json";
      payload = JSON.stringify(body);
    }
    let res: Response;
    try {
      res = await fetch(`${API_BASE}${path}`, { method, headers, body: payload, signal: composed });
    } catch (e) {
      // fetch only rejects on network failure / abort — map to a typed error.
      if (composed.aborted && (composed.reason as Error)?.name === "TimeoutError") {
        throw new ApiError(friendlyMessage(408), 408, "timeout");
      }
      if (composed.aborted) throw new ApiError("Request cancelled.", 0, "aborted");
      throw new ApiError(friendlyMessage(0), 0, "network");
    }
    if (!res.ok) {
      let detail: string | undefined;
      try {
        detail = extractDetail(await res.clone().json());
      } catch {
        /* non-JSON error body */
      }
      throw new ApiError(friendlyMessage(res.status, detail), res.status, "http");
    }
    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  } finally {
    done();
  }
}

export async function apiUpload<T>(path: string, form: FormData, signal?: AbortSignal): Promise<T> {
  return send<T>("POST", path, form, true, signal);
}

/**
 * Authenticated binary fetch for receipt preview/download. Returns the bytes as a Blob plus
 * the server-suggested filename (from Content-Disposition) — used to build an object URL for
 * inline preview or to trigger a download. Goes through the same timeout/abort/error path.
 */
export async function apiBlob(
  path: string,
  signal?: AbortSignal,
): Promise<{ blob: Blob; filename: string; contentType: string }> {
  const { signal: composed, done } = withTimeout(signal);
  try {
    const headers = { ...(await authHeader()) };
    let res: Response;
    try {
      res = await fetch(`${API_BASE}${path}`, { headers, signal: composed });
    } catch {
      if (composed.aborted && (composed.reason as Error)?.name === "TimeoutError") {
        throw new ApiError(friendlyMessage(408), 408, "timeout");
      }
      if (composed.aborted) throw new ApiError("Request cancelled.", 0, "aborted");
      throw new ApiError(friendlyMessage(0), 0, "network");
    }
    if (!res.ok) throw new ApiError(friendlyMessage(res.status), res.status, "http");
    const blob = await res.blob();
    const cd = res.headers.get("content-disposition") ?? "";
    const m = /filename\*?=(?:UTF-8'')?["']?([^"';]+)/i.exec(cd);
    const filename = m ? decodeURIComponent(m[1]) : "receipt";
    return { blob, filename, contentType: res.headers.get("content-type") ?? blob.type };
  } finally {
    done();
  }
}

export const apiGet = <T>(path: string, signal?: AbortSignal) => send<T>("GET", path, undefined, false, signal);
export const apiPost = <T>(path: string, body?: unknown, signal?: AbortSignal) =>
  send<T>("POST", path, body, false, signal);
export const apiPatch = <T>(path: string, body?: unknown, signal?: AbortSignal) =>
  send<T>("PATCH", path, body, false, signal);
export const apiDelete = <T>(path: string, signal?: AbortSignal) => send<T>("DELETE", path, undefined, false, signal);

/** Use the backend when enabled, otherwise the provided mock fallback. */
export function backend<T>(call: () => Promise<T>, fallback: () => Promise<T>): Promise<T> {
  return USE_BACKEND ? call() : fallback();
}
