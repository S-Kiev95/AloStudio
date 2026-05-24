"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
    // No enumeration: always show the same confirmation.
    setSent(true);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Recuperar contraseña</CardTitle>
        <p className="mt-1 text-sm text-fg-muted">
          Te enviamos un enlace para restablecerla.
        </p>
      </CardHeader>
      <CardContent>
        {sent ? (
          <div className="space-y-4">
            <p
              role="status"
              className="rounded-md border border-success/40 bg-success/10 px-3 py-2 text-sm text-success"
            >
              Si el email existe, vas a recibir instrucciones en unos minutos.
            </p>
            <Link href="/login" className="text-sm text-info hover:underline">
              Volver a iniciar sesión
            </Link>
          </div>
        ) : (
          <form
            onSubmit={handleSubmit(onSubmit)}
            className="space-y-4"
            noValidate
          >
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
              className="block text-center text-sm text-info hover:underline"
            >
              Volver a iniciar sesión
            </Link>
          </form>
        )}
      </CardContent>
    </Card>
  );
}
