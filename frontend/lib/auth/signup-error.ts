import { messageFromBody } from "@/lib/api/errors";
import { clientT } from "@/lib/i18n/client-t";
import type { MessageKey } from "@/lib/i18n/translate";

/** Why the backend refused the signup, in the visitor's language: FastAPI
 *  names the field that failed validation (``detail[].loc``), and the
 *  account builder answers in English (Chatwoot's messages). */
const FIELD_ERRORS: Record<string, MessageKey> = {
  email: "auth.signup.emailInvalid",
  password: "auth.signup.passwordMin",
  account_name: "auth.signup.accountNameLong",
  user_full_name: "auth.signup.fullNameLong",
};
const BUILDER_ERRORS: Record<string, MessageKey> = {
  "Email is invalid": "auth.signup.emailInvalid",
  "User already exists with the given email": "auth.signup.emailTaken",
  "Invalid params": "auth.signup.nameMissing",
};

export function signupError(body: unknown): string {
  const t = clientT();
  const b = (body ?? {}) as { detail?: unknown; message?: unknown };
  if (Array.isArray(b.detail)) {
    for (const item of b.detail) {
      const loc = (item as { loc?: unknown })?.loc;
      const field = Array.isArray(loc) ? String(loc[loc.length - 1]) : "";
      if (FIELD_ERRORS[field]) return t(FIELD_ERRORS[field]);
    }
  }
  if (typeof b.message === "string" && BUILDER_ERRORS[b.message]) return t(BUILDER_ERRORS[b.message]);
  return messageFromBody(body, t("auth.signup.failed"));
}
