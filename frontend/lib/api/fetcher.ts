import { ApiError, messageFromBody } from "./errors";

/**
 * Custom fetch mutator used by the orval-generated TanStack Query hooks.
 *
 * All browser requests go to the same-origin BFF proxy
 * (``NEXT_PUBLIC_API_BASE`` = ``/api/backend``) so httpOnly auth cookies
 * are sent automatically; the proxy re-attaches them as devise headers
 * server-side. On 401 we bounce to /login.
 *
 * Signature matches orval's ``httpClient: "fetch"`` mutator contract:
 * ``(url, options) => Promise<T>``.
 */
const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api/backend";

export async function apiFetch<T>(
  url: string,
  options?: RequestInit,
): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers ?? {}),
    },
  });

  if (res.status === 401 && typeof window !== "undefined") {
    window.location.href = "/login";
  }

  const text = await res.text();
  const body: unknown = text ? safeJson(text) : null;

  if (!res.ok) {
    throw new ApiError(
      res.status,
      messageFromBody(body, `request failed (${res.status})`),
      body,
    );
  }
  return body as T;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}
