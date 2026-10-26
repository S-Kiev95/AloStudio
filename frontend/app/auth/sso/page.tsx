"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { ThemeToggle } from "@/components/shell/theme-toggle";
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
    <div className="space-y-5">
      <div className="neon-sign">
        <h1 className="text-[28px] leading-[1.2]">Acceso desde Postiz</h1>
      </div>
      {error ? (
        <div className="space-y-4">
          <p
            role="alert"
            className="rounded-control border border-danger/40 bg-danger/10 px-3.5 py-2.5 text-sm text-danger"
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
    </div>
  );
}

export default function SsoPage() {
  return (
    <div className="relative flex min-h-dvh flex-col items-center justify-center p-4 sm:p-6">
      <div className="fixed right-3 top-3 z-20">
        <ThemeToggle />
      </div>
      <div className="glass-panel w-full max-w-[420px] rounded-panel bg-surface p-7 sm:p-9">
        <div className="mb-7">
          <span className="neon-wordmark inline-block select-none text-[38px] leading-none">
            AloStudio
          </span>
        </div>
        <Suspense>
          <SsoExchange />
        </Suspense>
      </div>
    </div>
  );
}
