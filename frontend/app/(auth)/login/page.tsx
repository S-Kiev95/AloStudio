"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { messageFromBody } from "@/lib/api/errors";
import { type LoginInput, loginSchema } from "@/lib/auth/schemas";

export default function LoginPage() {
  const router = useRouter();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginInput>({ resolver: zodResolver(loginSchema) });

  async function onSubmit(values: LoginInput) {
    setFormError(null);
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(values),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      setFormError(messageFromBody(body, "No se pudo iniciar sesión."));
      return;
    }
    router.push(body.accountId ? `/accounts/${body.accountId}` : "/accounts");
    router.refresh();
  }

  return (
    <div className="space-y-6">
      <div>
        <div className="neon-sign">
          <h1 className="text-[28px] leading-[1.2]">Iniciar sesión</h1>
        </div>
        <p className="mt-1.5 text-sm text-fg-muted">
          Accedé a tu cuenta de AloStudio.
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        {formError ? (
          <p
            role="alert"
            className="rounded-control border border-danger/40 bg-danger/10 px-3.5 py-2.5 text-sm text-danger"
          >
            {formError}
          </p>
        ) : null}

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

        <div className="space-y-1.5">
          <Label htmlFor="password" required>
            Contraseña
          </Label>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            aria-invalid={Boolean(errors.password)}
            aria-describedby={errors.password ? "password-error" : undefined}
            {...register("password")}
          />
          {errors.password ? (
            <p id="password-error" role="alert" className="text-sm text-danger">
              {errors.password.message}
            </p>
          ) : null}
        </div>

        <Button type="submit" className="w-full" loading={isSubmitting}>
          Entrar
        </Button>

        <Link
          href="/forgot-password"
          className="block pt-1 text-center text-sm text-info hover:underline"
        >
          ¿Olvidaste tu contraseña?
        </Link>
      </form>
    </div>
  );
}
