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
            <svg aria-hidden viewBox="0 0 24 24" className="h-4 w-4">
              <path fill="#EA4335" d="M12 10.2v3.9h5.4c-.24 1.4-1.66 4.1-5.4 4.1-3.25 0-5.9-2.69-5.9-6s2.65-6 5.9-6c1.85 0 3.09.79 3.8 1.47l2.59-2.5C16.73 3.6 14.6 2.6 12 2.6 6.82 2.6 2.6 6.82 2.6 12s4.22 9.4 9.4 9.4c5.43 0 9.03-3.81 9.03-9.19 0-.62-.07-1.09-.15-1.56H12z" />
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
