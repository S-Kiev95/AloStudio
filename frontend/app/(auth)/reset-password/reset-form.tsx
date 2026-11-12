"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { errorKey, type ResetInput, resetSchema } from "@/lib/auth/schemas";
import { useT } from "@/lib/i18n/provider";

export function ResetForm({ token }: { token: string }) {
  const router = useRouter();
  const t = useT();
  const [formError, setFormError] = useState<string | null>(null);
  const [linkExpired, setLinkExpired] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ResetInput>({ resolver: zodResolver(resetSchema) });

  async function onSubmit(values: ResetInput) {
    setFormError(null);
    setLinkExpired(false);
    const res = await fetch("/api/auth/reset-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        token,
        password: values.password,
        passwordConfirmation: values.passwordConfirmation,
      }),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      // The backend says only this, whether the link expired or was used.
      if (body?.message === "Invalid token") {
        setLinkExpired(true);
        setFormError(t("auth.reset.expired"));
        return;
      }
      setFormError(
        body?.message ?? body?.errors?.[0] ?? t("auth.reset.failed"),
      );
      return;
    }
    router.push(body.accountId ? `/accounts/${body.accountId}` : "/accounts");
    router.refresh();
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
      {formError ? (
        <p
          role="alert"
          className="rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger"
        >
          {formError}
          {linkExpired ? (
            <>
              {" "}
              <Link href="/forgot-password" className="font-medium underline">
                {t("auth.reset.requestNewLink")}
              </Link>
            </>
          ) : null}
        </p>
      ) : null}
      <div className="space-y-1.5">
        <Label htmlFor="password" required>
          {t("auth.reset.newPassword")}
        </Label>
        <Input
          id="password"
          type="password"
          autoComplete="new-password"
          aria-invalid={Boolean(errors.password)}
          {...register("password")}
        />
        {errors.password ? (
          <p role="alert" className="text-sm text-danger">
            {t(errorKey(errors.password.message))}
          </p>
        ) : null}
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="passwordConfirmation" required>
          {t("auth.reset.repeatPassword")}
        </Label>
        <Input
          id="passwordConfirmation"
          type="password"
          autoComplete="new-password"
          aria-invalid={Boolean(errors.passwordConfirmation)}
          {...register("passwordConfirmation")}
        />
        {errors.passwordConfirmation ? (
          <p role="alert" className="text-sm text-danger">
            {t(errorKey(errors.passwordConfirmation.message))}
          </p>
        ) : null}
      </div>
      <Button type="submit" className="w-full" loading={isSubmitting}>
        {t("auth.reset.submit")}
      </Button>
    </form>
  );
}
