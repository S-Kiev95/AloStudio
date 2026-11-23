import { messageFromBody } from "@/lib/api/errors";

/** Why the backend refused the signup, in the words of this screen:
 *  FastAPI names the field that failed validation (``detail[].loc``), and
 *  the account builder answers in English (Chatwoot's messages). */
const FIELD_ERRORS: Record<string, string> = {
  email: "El correo no es válido. Revisalo y probá de nuevo.",
  password: "La contraseña tiene que tener entre 8 y 72 caracteres.",
  account_name: "El nombre del negocio es demasiado largo.",
  user_full_name: "Tu nombre es demasiado largo.",
};
const BUILDER_ERRORS: Record<string, string> = {
  "Email is invalid": FIELD_ERRORS.email,
  "User already exists with the given email": "Ya hay una cuenta con ese correo. Iniciá sesión o recuperá la contraseña.",
  "Invalid params": "Completá el nombre del negocio o tu nombre.",
};

export function signupError(body: unknown): string {
  const b = (body ?? {}) as { detail?: unknown; message?: unknown };
  if (Array.isArray(b.detail)) {
    for (const item of b.detail) {
      const loc = (item as { loc?: unknown })?.loc;
      const field = Array.isArray(loc) ? String(loc[loc.length - 1]) : "";
      if (FIELD_ERRORS[field]) return FIELD_ERRORS[field];
    }
  }
  if (typeof b.message === "string" && BUILDER_ERRORS[b.message]) return BUILDER_ERRORS[b.message];
  return messageFromBody(body, "No se pudo crear la cuenta.");
}
