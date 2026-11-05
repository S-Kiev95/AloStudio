"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { Facebook } from "@/components/ui/brand-icons";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/errors";
import {
  startFacebookPageOAuth,
  useConnectPendingPage,
  usePendingFacebookPages,
} from "@/lib/api/inboxes";

/** Connects a Page by logging in with Facebook. Facebook sends the browser
 *  back here with `fb_pick` (several Pages to choose from) or `fb_error`. */
function FacebookPageConnectInner({ accountId }: { accountId: string }) {
  const router = useRouter();
  const params = useSearchParams();
  const nonce = params.get("fb_pick");
  const pages = usePendingFacebookPages(accountId, nonce);
  const connect = useConnectPendingPage(accountId);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(params.get("fb_error"));

  const message = (err: unknown, fallback: string) =>
    err instanceof ApiError ? err.message : fallback;

  async function start() {
    setError(null);
    setStarting(true);
    try {
      await startFacebookPageOAuth(accountId);
    } catch (err) {
      setError(message(err, "No se pudo iniciar la conexión."));
      setStarting(false);
    }
  }

  async function choose(pageId: string) {
    if (!nonce) return;
    setError(null);
    try {
      const result = await connect.mutateAsync({ nonce, pageId });
      router.push(`/accounts/${accountId}/settings/inboxes/${result.inbox_id}`);
    } catch (err) {
      setError(message(err, "No se pudo conectar la Página."));
    }
  }

  const shownError =
    error ??
    (pages.isError
      ? message(pages.error, "No se pudieron leer las Páginas. Volvé a conectar con Facebook.")
      : null);

  return (
    <div className="space-y-3 rounded-md border border-glass bg-surface p-5">
      {shownError ? (
        <p
          role="alert"
          className="rounded-control border border-danger bg-surface-2 px-3 py-2 text-sm text-danger"
        >
          {shownError}
        </p>
      ) : null}

      {nonce && pages.data ? (
        <div className="space-y-2">
          <p className="text-sm font-medium text-fg">¿Qué Página querés conectar?</p>
          {pages.data.map((page) => (
            <Button
              key={page.id}
              type="button"
              variant="simple"
              className="w-full justify-start"
              disabled={connect.isPending}
              onClick={() => void choose(page.id)}
            >
              <Facebook className="h-4 w-4" aria-hidden />
              {page.name ?? page.id}
            </Button>
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          <p className="text-sm text-fg-muted">
            Iniciá sesión con Facebook y elegí la Página. La bandeja se crea
            sola, con su nombre.
          </p>
          <Button type="button" loading={starting} onClick={() => void start()}>
            <Facebook mono className="h-4 w-4" aria-hidden />
            Conectar con Facebook
          </Button>
        </div>
      )}
      <p className="border-t border-glass pt-3 text-xs text-fg-muted">
        También podés cargar los datos a mano en el formulario de abajo.
      </p>
    </div>
  );
}

export function FacebookPageConnect({ accountId }: { accountId: string }) {
  return (
    <Suspense>
      <FacebookPageConnectInner accountId={accountId} />
    </Suspense>
  );
}
