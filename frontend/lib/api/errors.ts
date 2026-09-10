/**
 * Normalises the backend's error envelopes into one shape.
 *
 * The FastAPI backend mirrors Chatwoot, so errors arrive as one of:
 *   - ``{"message": "..."}``                     (ChatwootHTTPException)
 *   - ``{"error": "..."}``                        (RecordNotFound etc.)
 *   - ``{"errors": ["...", ...]}``                (devise auth)
 *   - ``{"detail": ...}``                         (FastAPI default)
 *
 * Those strings are written for a Chatwoot-compatible API client, in
 * English, and they reach the screen as they are. Where the backend also
 * sends a ``code`` we say it in our own words instead — see
 * ``WORDING_BY_CODE``.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly body: unknown;

  constructor(
    status: number,
    message: string,
    body: unknown,
    code?: string,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
    this.code = code;
  }
}

/**
 * Backend error codes we have our own wording for.
 *
 * Keyed on ``code`` and never on the English message. That message is the
 * Chatwoot-compatible string an external client reads, so the backend has
 * to keep sending it exactly as it does; matching on it here would tie our
 * copy to wording that exists for somebody else, and would come undone the
 * day a typo in it is fixed.
 */
const WORDING_BY_CODE: Record<string, string> = {
  not_authorized: "No tenés permiso para hacer esto.",
};

export function messageFromBody(body: unknown, fallback: string): string {
  if (body && typeof body === "object") {
    const b = body as Record<string, unknown>;
    const ours =
      typeof b.code === "string" ? WORDING_BY_CODE[b.code] : undefined;
    if (ours) return ours;
    if (typeof b.message === "string") return b.message;
    if (typeof b.error === "string") return b.error;
    if (Array.isArray(b.errors) && typeof b.errors[0] === "string") {
      return b.errors.join(", ");
    }
    if (typeof b.detail === "string") return b.detail;
  }
  return fallback;
}
