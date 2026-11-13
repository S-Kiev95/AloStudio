import { z } from "zod";

import type { MessageKey } from "@/lib/i18n/translate";

// Error messages are message keys: the form shows them with `t()`, in the
// visitor's language. `satisfies` keeps each one a real key.
const V = {
  emailInvalid: "validation.emailInvalid",
  passwordRequired: "validation.passwordRequired",
  passwordMin: "validation.passwordMin",
  confirmPassword: "validation.confirmPassword",
  passwordsDontMatch: "validation.passwordsDontMatch",
} as const satisfies Record<string, MessageKey>;

/** A zod error message as a message key, for `t()`. */
export function errorKey(message: string | undefined): MessageKey {
  return (message ?? V.emailInvalid) as MessageKey;
}

export const loginSchema = z.object({
  email: z.string().email(V.emailInvalid),
  password: z.string().min(1, V.passwordRequired),
});

export type LoginInput = z.infer<typeof loginSchema>;

export const forgotSchema = z.object({
  email: z.string().email(V.emailInvalid),
});

export type ForgotInput = z.infer<typeof forgotSchema>;

export const resetSchema = z
  .object({
    password: z.string().min(6, V.passwordMin),
    passwordConfirmation: z.string().min(1, V.confirmPassword),
  })
  .refine((v) => v.password === v.passwordConfirmation, {
    message: V.passwordsDontMatch,
    path: ["passwordConfirmation"],
  });

export type ResetInput = z.infer<typeof resetSchema>;
