"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { errorKey, type ForgotInput, forgotSchema } from "@/lib/auth/schemas";
import { useT } from "@/lib/i18n/provider";

export default function ForgotPasswordPage() {
  const [sent, setSent] = useState(false);
  const t = useT();
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
          <h1 className="text-[28px] leading-[1.2]">{t("auth.forgot.title")}</h1>
        </div>
        <p className="mt-1.5 text-sm text-fg-muted">
          {t("auth.forgot.subtitle")}
        </p>
      </div>

      {sent ? (
        <div className="space-y-4">
          <p
            role="status"
            className="rounded-control border border-success/40 bg-success/10 px-3.5 py-2.5 text-sm text-success"
          >
            {t("auth.forgot.sent")}
          </p>
          <Link href="/login" className="inline-block text-sm text-info hover:underline">
            {t("auth.forgot.backToLogin")}
          </Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div className="space-y-1.5">
            <Label htmlFor="email" required>
              {t("common.email")}
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
                {t(errorKey(errors.email.message))}
              </p>
            ) : null}
          </div>
          <Button type="submit" className="w-full" loading={isSubmitting}>
            {t("auth.forgot.submit")}
          </Button>
          <Link
            href="/login"
            className="block pt-1 text-center text-sm text-info hover:underline"
          >
            {t("auth.forgot.backToLogin")}
          </Link>
        </form>
      )}
    </div>
  );
}
