"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { messageFromBody } from "@/lib/api/errors";

/**
 * SSO landing page: Postiz redirects the browser here with a short-lived
 * signed JWT. We hand it to the BFF (`/api/auth/sso`), which exchanges it
 * for the devise session cookies, then send the user to their account.
 */
function SsoExchange() {
  const router = useRouter();
  const params = useSearchParams();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = params.get("token");
    if (!token) {
      setError("El enlace de acceso no incluye un token.");
      return;
    }
    let cancelled = false;
    (async () => {
      const res = await fetch("/api/auth/sso", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      const body = await res.json().catch(() => ({}));
      if (cancelled) return;
      if (!res.ok) {
        setError(
          messageFromBody(
            body,
            "No se pudo iniciar sesión. El enlace puede haber caducado.",
          ),
        );
        return;
      }
      router.push(body.accountId ? `/accounts/${body.accountId}` : "/accounts");
      router.refresh();
    })();
    return () => {
      cancelled = true;
    };
  }, [params, router]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Acceso desde Postiz</CardTitle>
      </CardHeader>
      <CardContent>
        {error ? (
          <div className="space-y-4">
            <p
              role="alert"
              className="rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger"
            >
              {error}
            </p>
            <Link
              href="/login"
              className="block text-center text-sm text-info hover:underline"
            >
              Ir a iniciar sesión
            </Link>
          </div>
        ) : (
          <p className="text-sm text-fg-muted">Iniciando sesión…</p>
        )}
      </CardContent>
    </Card>
  );
}

export default function SsoPage() {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-6 bg-bg p-4">
      <span className="flex items-center gap-2.5">
        <span
          className="grid h-9 w-9 place-items-center rounded-lg text-base font-bold text-primary-fg shadow-[0_2px_12px_rgb(252_213_53/0.4)]"
          style={{ background: "var(--gradient-primary)" }}
        >
          A
        </span>
        <span className="text-xl font-semibold tracking-tight text-fg">
          AloStudio
        </span>
      </span>
      <div className="w-full max-w-sm">
        <Suspense>
          <SsoExchange />
        </Suspense>
      </div>
    </div>
  );
}
