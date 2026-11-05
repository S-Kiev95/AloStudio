"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { messageFromBody } from "@/lib/api/errors";
import { safeNextPath } from "@/lib/auth/next-path";
import { type LoginInput, loginSchema } from "@/lib/auth/schemas";

export default function LoginPage() {
  const router = useRouter();
  const [formError, setFormError] = useState<string | null>(null);
  const [googleEnabled, setGoogleEnabled] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/auth/google")
      .then((res) => res.json())
      .then((body) => {
        if (!cancelled) setGoogleEnabled(Boolean(body?.enabled));
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);
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
    // Back to where the session ran out (or the OAuth consent), if it is
    // a page of this app.
    const next = safeNextPath(
      new URLSearchParams(window.location.search).get("next"),
    );
    router.push(
      next ?? (body.accountId ? `/accounts/${body.accountId}` : "/accounts"),
    );
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

      {googleEnabled ? (
        <div className="space-y-4">
          {/* A plain link: the route sends the browser on to Google. */}
          <a
            href="/api/auth/google/start"
            className="flex h-11 w-full items-center justify-center gap-2.5 rounded-control border border-glass bg-field text-sm font-medium text-fg transition-colors hover:bg-hover-glass"
          >
            <svg aria-hidden viewBox="0 0 48 48" className="h-4 w-4">
              <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
              <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
              <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
              <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
            </svg>
            Entrar con Google
          </a>
          <div className="flex items-center gap-3 text-xs text-fg-muted">
            <span className="h-px flex-1 bg-glass" />
            o con tu correo
            <span className="h-px flex-1 bg-glass" />
          </div>
        </div>
      ) : null}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        {formError ? (
          <p
            role="alert"
            className="rounded-control border border-danger bg-surface-2 px-3.5 py-2.5 text-sm text-danger"
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
