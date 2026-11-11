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
import { usePublicInstallation } from "@/lib/api/installation";
import { safeNextPath } from "@/lib/auth/next-path";
import { type SignupInput, signupSchema } from "@/lib/auth/schemas";

export default function RegistroPage() {
  const router = useRouter();
  const installation = usePublicInstallation();
  const [formError, setFormError] = useState<string | null>(null);
  const [signupClosed, setSignupClosed] = useState(false);
  const [pendingEmail, setPendingEmail] = useState<string | null>(null);
  const [resending, setResending] = useState(false);
  const [resent, setResent] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<SignupInput>({ resolver: zodResolver(signupSchema) });

  async function onSubmit(values: SignupInput) {
    setFormError(null);
    const res = await fetch("/api/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(values),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      if (res.status === 404) {
        setSignupClosed(true);
        return;
      }
      if (res.status === 429) {
        const msg =
          typeof (body as { message?: unknown })?.message === "string" &&
          (body as { message: string }).message
            ? (body as { message: string }).message
            : "Demasiados registros seguidos. Probá más tarde.";
        setFormError(msg);
        return;
      }
      setFormError(messageFromBody(body, "No se pudo crear la cuenta."));
      return;
    }

    const emailOnly =
      typeof (body as { email?: unknown })?.email === "string" &&
      !(body as { accountId?: unknown })?.accountId &&
      !(body as { data?: unknown })?.data;
    if (emailOnly) {
      setPendingEmail((body as { email: string }).email);
      return;
    }

    const accountId =
      (body as { accountId?: number | null })?.accountId ??
      (body as { data?: { account_id?: number | null } })?.data?.account_id ??
      null;
    const next = safeNextPath(
      new URLSearchParams(window.location.search).get("next"),
    );
    router.push(next ?? (accountId ? `/accounts/${accountId}` : "/accounts"));
    router.refresh();
  }

  async function resendConfirmation() {
    if (!pendingEmail) return;
    setResending(true);
    setResent(false);
    try {
      await fetch("/api/auth/resend-confirmation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: pendingEmail }),
      });
      setResent(true);
    } finally {
      setResending(false);
    }
  }

  if (installation.data?.signup_enabled === false || signupClosed) {
    return (
      <div className="space-y-6">
        <div>
          <div className="neon-sign">
            <h1 className="text-[28px] leading-[1.2]">Crear cuenta</h1>
          </div>
        </div>
        <p
          role="alert"
          className="rounded-control border border-glass bg-surface-2 px-3.5 py-2.5 text-sm text-fg"
        >
          El registro no está abierto en esta instalación
        </p>
        <Link
          href="/login"
          className="block text-center text-sm text-info hover:underline"
        >
          Ir a iniciar sesión
        </Link>
      </div>
    );
  }

  if (pendingEmail) {
    return (
      <div className="space-y-6">
        <div>
          <div className="neon-sign">
            <h1 className="text-[28px] leading-[1.2]">Confirmá tu correo</h1>
          </div>
        </div>
        <p
          role="status"
          className="rounded-control border border-glass bg-surface-2 px-3.5 py-2.5 text-sm text-fg"
        >
          Te mandamos un correo a {pendingEmail}. Abrilo para activar tu cuenta
        </p>
        {resent ? (
          <p className="text-xs text-fg-muted">
            Te volvimos a mandar el correo de confirmación.
          </p>
        ) : null}
        <Button
          type="button"
          variant="secondary"
          className="w-full"
          loading={resending}
          onClick={() => void resendConfirmation()}
        >
          Reenviar correo
        </Button>
        <Link
          href="/login"
          className="block text-center text-sm text-info hover:underline"
        >
          Ir a iniciar sesión
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <div className="neon-sign">
          <h1 className="text-[28px] leading-[1.2]">Crear cuenta</h1>
        </div>
        <p className="mt-1.5 text-sm text-fg-muted">
          Creá tu cuenta de AloStudio.
        </p>
      </div>

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
          <Label htmlFor="account_name" required>
            Nombre de la empresa
          </Label>
          <Input
            id="account_name"
            type="text"
            autoComplete="organization"
            aria-invalid={Boolean(errors.account_name)}
            aria-describedby={
              errors.account_name ? "account_name-error" : undefined
            }
            {...register("account_name")}
          />
          {errors.account_name ? (
            <p
              id="account_name-error"
              role="alert"
              className="text-sm text-danger"
            >
              {errors.account_name.message}
            </p>
          ) : null}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="user_full_name" required>
            Tu nombre
          </Label>
          <Input
            id="user_full_name"
            type="text"
            autoComplete="name"
            aria-invalid={Boolean(errors.user_full_name)}
            aria-describedby={
              errors.user_full_name ? "user_full_name-error" : undefined
            }
            {...register("user_full_name")}
          />
          {errors.user_full_name ? (
            <p
              id="user_full_name-error"
              role="alert"
              className="text-sm text-danger"
            >
              {errors.user_full_name.message}
            </p>
          ) : null}
        </div>

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
            autoComplete="new-password"
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
          Crear cuenta
        </Button>

        <Link
          href="/login"
          className="block pt-1 text-center text-sm text-info hover:underline"
        >
          ¿Ya tenés cuenta? Iniciá sesión
        </Link>
      </form>
    </div>
  );
}
