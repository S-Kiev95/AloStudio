"use client";

import { Facebook, Instagram } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { startOAuth, useInstagramInboxes } from "@/lib/api/instagram";

import { ConnectedChannelCard } from "./connected-channel-card";
import { ManualConnectForm } from "./manual-connect-form";

export function InstagramConnection({ accountId }: { accountId: string }) {
  const inboxes = useInstagramInboxes(accountId);
  const [showManual, setShowManual] = useState(false);
  const [oauthError, setOauthError] = useState<string | null>(null);

  async function connect(flow: "facebook" | "instagram") {
    setOauthError(null);
    try {
      await startOAuth(accountId, flow);
    } catch {
      setOauthError(
        "No se pudo iniciar la conexión. ¿Está configurado META en el backend?",
      );
    }
  }

  return (
    <div className="space-y-6">
      {/* Connected channels */}
      <Card>
        <CardHeader>
          <CardTitle>Cuentas conectadas</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {inboxes.isLoading ? (
            <p className="text-sm text-fg-muted">Cargando…</p>
          ) : inboxes.isError ? (
            <p role="alert" className="text-sm text-danger">
              No se pudieron cargar las cuentas.
            </p>
          ) : (inboxes.data?.length ?? 0) === 0 ? (
            <p className="text-sm text-fg-muted">
              Todavía no hay ninguna cuenta de Instagram conectada.
            </p>
          ) : (
            inboxes.data?.map((ib) => (
              <ConnectedChannelCard
                key={ib.id}
                accountId={accountId}
                inbox={ib}
              />
            ))
          )}
        </CardContent>
      </Card>

      {/* Connect new */}
      <Card>
        <CardHeader>
          <CardTitle>Conectar una cuenta</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {oauthError ? (
            <p role="alert" className="text-sm text-danger">
              {oauthError}
            </p>
          ) : null}
          <div className="flex flex-wrap gap-3">
            <Button onClick={() => connect("facebook")}>
              <Facebook className="h-4 w-4" aria-hidden />
              Facebook Login
            </Button>
            <Button variant="secondary" onClick={() => connect("instagram")}>
              <Instagram className="h-4 w-4" aria-hidden />
              Instagram Login
            </Button>
          </div>
          <p className="text-xs text-fg-muted">
            Facebook Login requiere una Página de Facebook y permite borrar
            publicaciones. Instagram Login no necesita Página, pero no permite
            borrar por API.
          </p>

          <div className="border-t border-border pt-4">
            <button
              type="button"
              onClick={() => setShowManual((v) => !v)}
              className="text-sm text-info hover:underline"
            >
              {showManual ? "Ocultar" : "Modo avanzado: pegar un token"}
            </button>
            {showManual ? (
              <div className="mt-3">
                <ManualConnectForm accountId={accountId} />
              </div>
            ) : null}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
