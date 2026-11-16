import { translateOr, type MessageKey } from "@/lib/i18n/translate";
import { clientT } from "@/lib/i18n/client-t";

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
const WORDING_BY_CODE: Record<string, MessageKey> = {
  // From the backend (app/core/errors.py adds most of them centrally)
  not_authorized: "apiErrors.notAuthorized",
  too_many_attempts: "apiErrors.tooManyAttempts",
  not_found: "apiErrors.notFound",
  validation_failed: "apiErrors.validationFailed",
  invalid_login: "apiErrors.invalidLogin",
  sign_in_required: "apiErrors.signInRequired",
  invalid_token: "apiErrors.invalidToken",
  invalid_sso_token: "apiErrors.invalidSsoToken",
  sso_disabled: "apiErrors.ssoDisabled",
  google_disabled: "apiErrors.googleDisabled",
  google_unreachable: "apiErrors.googleUnreachable",
  scheduled_in_past: "apiErrors.scheduledInPast",
  phone_taken: "apiErrors.phoneTaken",
  blank: "apiErrors.blank",
  taken: "apiErrors.taken",
  // From our own route handlers (app/api/auth/*)
  missing_fields: "apiErrors.missingFields",
  server_unreachable: "apiErrors.serverUnreachable",
  no_session: "apiErrors.noSession",
  google_expired: "apiErrors.googleExpired",
  sso_token_missing: "apiErrors.ssoTokenMissing",
};

export function messageFromBody(body: unknown, fallback: string): string {
  if (body && typeof body === "object") {
    const b = body as Record<string, unknown>;
    const ours =
      typeof b.code === "string" ? WORDING_BY_CODE[b.code] : undefined;
    if (ours) {
      const t = clientT();
      // "blank" / "taken" name the field: in our words when we know it.
      const field =
        typeof b.field === "string"
          ? translateOr(t, `apiErrors.fields.${b.field}`, b.field) // i18n-ignore
          : "";
      return t(ours, { field });
    }
    if (typeof b.message === "string") return b.message;
    if (typeof b.error === "string") return b.error;
    if (Array.isArray(b.errors) && typeof b.errors[0] === "string") {
      return b.errors.join(", ");
    }
    if (typeof b.detail === "string") return b.detail;
  }
  return fallback;
}
