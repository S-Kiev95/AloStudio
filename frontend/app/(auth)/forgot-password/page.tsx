"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { type ForgotInput, forgotSchema } from "@/lib/auth/schemas";

export default function ForgotPasswordPage() {
  const [sent, setSent] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ForgotInput>({ resolver: zodResolver(forgotSchema) });

  async function onSubmit(values: ForgotInput) {
    await fetch("/api/auth/forgot-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(values),
    });
    setSent(true);
  }

  return (
    <div className="space-y-6">
      <div>
        <div className="neon-sign">
          <h1 className="text-[28px] leading-[1.2]">Recuperar contraseña</h1>
        </div>
        <p className="mt-1.5 text-sm text-fg-muted">
          Te enviamos un enlace para restablecerla.
        </p>
      </div>

      {sent ? (
        <div className="space-y-4">
          <p
            role="status"
            className="rounded-control border border-success/40 bg-success/10 px-3.5 py-2.5 text-sm text-success"
          >
            Si el email existe, vas a recibir instrucciones en unos minutos.
          </p>
          <Link href="/login" className="inline-block text-sm text-info hover:underline">
            Volver a iniciar sesión
          </Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div className="space-y-1.5">
            <Label htmlFor="email" required>
              Email
            </Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              aria-invalid={Boolean(errors.email)}
              aria-describedby={errors.email ? "email-error" : undefined}
              {...register("email")}
            />
            {errors.email ? (
              <p id="email-error" role="alert" className="text-sm text-danger">
                {errors.email.message}
              </p>
            ) : null}
          </div>
          <Button type="submit" className="w-full" loading={isSubmitting}>
            Enviar enlace
          </Button>
          <Link
            href="/login"
            className="block pt-1 text-center text-sm text-info hover:underline"
          >
            Volver a iniciar sesión
          </Link>
        </form>
      )}
    </div>
  );
}
