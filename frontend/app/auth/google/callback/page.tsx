"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";

import { NeonWordmark } from "@/components/brand/neon-wordmark";
import { ThemeToggle } from "@/components/shell/theme-toggle";
import { messageFromBody } from "@/lib/api/errors";

/**
 * Google sends the browser back here with `code` and `state`. We hand them
 * to the BFF (`/api/auth/google`), which signs the user in if an
 * administrator invited them, then send them to their account.
 */
function GoogleExchange() {
  const router = useRouter();
  const params = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  // The code works once: never post it twice (React may run effects twice).
  const sent = useRef(false);

  useEffect(() => {
    if (sent.current) return;
    sent.current = true;
    const code = params.get("code");
    const state = params.get("state");
    if (params.get("error") || !code || !state) {
      setError("Se canceló el ingreso con Google.");
      return;
    }
    (async () => {
      const res = await fetch("/api/auth/google", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code, state }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(messageFromBody(body, "No se pudo entrar con Google."));
        return;
      }
      router.push(body.accountId ? `/accounts/${body.accountId}` : "/accounts");
      router.refresh();
    })();
  }, [params, router]);

  return (
    <div className="space-y-5">
      <div className="neon-sign">
        <h1 className="text-[28px] leading-[1.2]">Ingreso con Google</h1>
      </div>
      {error ? (
        <div className="space-y-4">
          <p
            role="alert"
            className="rounded-control border border-danger bg-surface-2 px-3.5 py-2.5 text-sm text-danger"
          >
            {error}
          </p>
          <Link
            href="/login"
            className="block text-center text-sm text-info hover:underline"
          >
            Volver a iniciar sesión
          </Link>
        </div>
      ) : (
        <p className="text-sm text-fg-muted">Iniciando sesión…</p>
      )}
    </div>
  );
}

export default function GoogleCallbackPage() {
  return (
    <div className="relative flex min-h-dvh flex-col items-center justify-center p-4 sm:p-6">
      <div className="fixed right-3 top-3 z-20">
        <ThemeToggle />
      </div>
      <div className="page-enter glass-panel w-full max-w-[420px] rounded-panel bg-surface p-7 sm:p-9">
        <div className="mb-7">
          <NeonWordmark className="text-[38px]" />
        </div>
        <Suspense>
          <GoogleExchange />
        </Suspense>
      </div>
    </div>
  );
}
