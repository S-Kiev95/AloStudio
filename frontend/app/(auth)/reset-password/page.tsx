import Link from "next/link";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import { ResetForm } from "./reset-form";

/**
 * Reads the `reset_password_token` from the URL server-side (avoids the
 * useSearchParams Suspense bailout) and hands it to the client form.
 * Backend link uses `?reset_password_token=` / `?token=` — accept both.
 */
export default async function ResetPasswordPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const raw = sp.reset_password_token ?? sp.token;
  const token = Array.isArray(raw) ? raw[0] : raw;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Nueva contraseña</CardTitle>
      </CardHeader>
      <CardContent>
        {token ? (
          <ResetForm token={token} />
        ) : (
          <div className="space-y-3">
            <p role="alert" className="text-sm text-danger">
              Enlace inválido o incompleto.
            </p>
            <Link
              href="/forgot-password"
              className="text-sm text-info hover:underline"
            >
              Pedir un nuevo enlace
            </Link>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
