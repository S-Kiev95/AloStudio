import { z } from "zod";

export const loginSchema = z.object({
  email: z.string().email("Email inválido"),
  password: z.string().min(1, "La contraseña es obligatoria"),
});

export type LoginInput = z.infer<typeof loginSchema>;

export const forgotSchema = z.object({
  email: z.string().email("Email inválido"),
});

export type ForgotInput = z.infer<typeof forgotSchema>;

export const resetSchema = z
  .object({
    password: z.string().min(6, "Mínimo 6 caracteres"),
    passwordConfirmation: z.string().min(1, "Confirmá la contraseña"),
  })
  .refine((v) => v.password === v.passwordConfirmation, {
    message: "Las contraseñas no coinciden",
    path: ["passwordConfirmation"],
  });

export type ResetInput = z.infer<typeof resetSchema>;
