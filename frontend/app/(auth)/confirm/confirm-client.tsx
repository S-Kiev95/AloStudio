"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { buttonVariants } from "@/components/ui/button";

type Status = "working" | "error" | "missing";

export function ConfirmClient({ token }: { token: string | null }) {
  const router = useRouter();
  const [status, setStatus] = useState<Status>(token ? "working" : "missing");
  const [message, setMessage] = useState<string | null>(null);
  const ran = useRef(false);

  useEffect(() => {
    if (!token || ran.current) return;
    ran.current = true; // StrictMode runs effects twice in dev — guard it.
    (async () => {
      const res = await fetch("/api/auth/confirmation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      const body = await res.json().catch(() => ({}));
      if (res.ok) {
        router.push(
          body.accountId ? `/accounts/${body.accountId}` : "/accounts",
        );
        router.refresh();
        return;
      }
      setStatus("error");
      setMessage(body?.message ?? "No se pudo confirmar el email.");
    })();
  }, [token, router]);

  if (status === "working") {
    return (
      <p role="status" className="text-sm text-fg-muted">
        Confirmando tu cuenta…
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <p role="alert" className="text-sm text-danger">
        {status === "missing"
          ? "Falta el token de confirmación en el enlace."
          : message}
      </p>
      <Link
        href="/login"
        className={buttonVariants({ variant: "secondary", size: "sm" })}
      >
        Ir a iniciar sesión
      </Link>
    </div>
  );
}
