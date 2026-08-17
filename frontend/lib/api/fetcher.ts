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

  const text = await res.text();
  const body: unknown = text ? safeJson(text) : null;

  // A 401 means two different things here. The API keeps Chatwoot's shape,
  // where "signed in but not an administrator" is also a 401 — so bouncing
  // on every 401 threw an agent back to the login screen the moment a page
  // touched an admin-only endpoint, which looked like the session dying
  // seconds after signing in. Only a real authentication failure should
  // send someone to /login; a permission denial belongs in the panel that
  // asked for it.
  if (res.status === 401 && typeof window !== "undefined" && !isDenial(body)) {
    window.location.href = "/login";
  }

  if (!res.ok) {
    throw new ApiError(
      res.status,
      messageFromBody(body, `request failed (${res.status})`),
      body,
    );
  }
  return body as T;
}

/** True when a 401 is "you are not allowed", not "you are not signed in".
 *
 *  Keyed on `code` rather than the message: the message is the
 *  Chatwoot-compatible string an external client reads, so matching it here
 *  would tie the redirect to wording that exists for someone else. */
function isDenial(body: unknown): boolean {
  return (
    typeof body === "object" &&
    body !== null &&
    (body as { code?: unknown }).code === "not_authorized"
  );
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}
