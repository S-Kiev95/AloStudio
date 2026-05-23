/**
 * Normalises the backend's error envelopes into one shape.
 *
 * The FastAPI backend mirrors Chatwoot, so errors arrive as one of:
 *   - ``{"message": "..."}``                     (ChatwootHTTPException)
 *   - ``{"error": "..."}``                        (RecordNotFound etc.)
 *   - ``{"errors": ["...", ...]}``                (devise auth)
 *   - ``{"detail": ...}``                         (FastAPI default)
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

export function messageFromBody(body: unknown, fallback: string): string {
  if (body && typeof body === "object") {
    const b = body as Record<string, unknown>;
    if (typeof b.message === "string") return b.message;
    if (typeof b.error === "string") return b.error;
    if (Array.isArray(b.errors) && typeof b.errors[0] === "string") {
      return b.errors.join(", ");
    }
    if (typeof b.detail === "string") return b.detail;
  }
  return fallback;
}
