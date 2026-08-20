"use client";

import { Facebook, Instagram } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { startOAuth, useInstagramInboxes } from "@/lib/api/instagram";

import { ConnectedChannelCard } from "./connected-channel-card";
import { ManualConnectForm } from "./manual-connect-form";

/** What the OAuth callback redirected back with (see the backend's
 *  `_back_to_dashboard`): `ig=connected|reconnected` + `ig_login` +
 *  `ig_user`, or `ig_error=<mensaje>`. */
function outcomeMessage(
  ig: string | null,
  login: string | null,
  user: string | null,
): string | null {
  if (ig !== "connected" && ig !== "reconnected") return null;
  const flow = login === "instagram" ? "Instagram Login" : "Facebook Login";
  // Meta doesn't always hand back the handle; say "Cuenta" when it didn't.
  const who = user ? `@${user}` : "Cuenta";
  return ig === "reconnected"
    ? `${who} reconectada por ${flow}. Se renovó el token de la cuenta que ya tenías.`
    : `${who} conectada por ${flow}.`;
}

export function InstagramConnection({ accountId }: { accountId: string }) {
  const inboxes = useInstagramInboxes(accountId);
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const [showManual, setShowManual] = useState(false);
  const [oauthError, setOauthError] = useState<string | null>(
    searchParams.get("ig_error"),
  );
  const [oauthSuccess] = useState<string | null>(
    outcomeMessage(
      searchParams.get("ig"),
      searchParams.get("ig_login"),
      searchParams.get("ig_user"),
    ),
  );

  // Keep the banner but drop the params, so a refresh (or a shared link)
  // doesn't replay a result from a connection that already happened.
  useEffect(() => {
    if (searchParams.has("ig") || searchParams.has("ig_error")) {
      router.replace(pathname, { scroll: false });
    }
  }, [searchParams, router, pathname]);

  async function connect(flow: "facebook" | "instagram") {
    setOauthError(null);
    try {
      await startOAuth(accountId, flow);
    } catch (e) {
      // The backend names the missing settings; guessing on its behalf
      // sent the admin looking in the wrong place.
      setOauthError(
        (e as { message?: string })?.message ??
          "No se pudo iniciar la conexión.",
      );
    }
  }

  return (
    <div className="space-y-6">
      {/* Outcome of the OAuth round-trip */}
      {oauthSuccess ? (
        <p
          role="status"
          className="rounded-md border border-success/30 bg-success/5 px-3 py-2 text-sm text-success"
        >
          {oauthSuccess}
        </p>
      ) : null}

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
