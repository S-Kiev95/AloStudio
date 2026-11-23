"use client";

import { RefreshCw, ShoppingBag } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Facebook } from "@/components/ui/brand-icons";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  type MetaCatalog,
  startMetaCatalogLogin,
  useConnectPendingMetaCatalog,
  useMetaCatalogActions,
  usePendingMetaCatalogs,
} from "@/lib/api/crm";
import { useIntlTag, useT } from "@/lib/i18n/provider";
import { translateOr } from "@/lib/i18n/translate";
import { useConfirm } from "@/components/ui/confirm-dialog";

/** Our wording for a refusal, by the code the backend sends. */
function useCatalogError() {
  const t = useT();
  return (err: unknown) => {
    const code = (err as { body?: { code?: unknown } })?.body?.code;
    if (typeof code === "string" && code.startsWith("meta_catalog.")) {
      return translateOr(t, `metaCatalog.errors.${code.slice(13)}`, t("metaCatalog.errors.refused"));
    }
    return (err as { message?: string })?.message ?? t("metaCatalog.errors.refused");
  };
}

/** CRM → Productos: the Meta catalogue the products are sent to. Facebook
 *  sends the browser back here with `catalog=connected`, `catalog_pick`
 *  (several catalogues to choose from) or `catalog_error` (a code). */
export function MetaCatalogCard(props: { accountId: string; catalog: MetaCatalog }) {
  return (
    <Suspense>
      <MetaCatalogCardInner {...props} />
    </Suspense>
  );
}

function MetaCatalogCardInner({
  accountId,
  catalog,
}: {
  accountId: string;
  catalog: MetaCatalog;
}) {
  const confirm = useConfirm();
  const t = useT();
  const intlTag = useIntlTag();
  const errorText = useCatalogError();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const { connect, disconnect, sync } = useMetaCatalogActions(accountId);
  // Read once on arrival from Facebook: the query string is cleared after.
  const [arrival] = useState(() => ({
    pick: params.get("catalog_pick"),
    error: params.get("catalog_error"),
    connected: params.get("catalog") === "connected",
  }));
  const [nonce, setNonce] = useState<string | null>(arrival.pick);
  const pending = usePendingMetaCatalogs(accountId, nonce);
  const choose = useConnectPendingMetaCatalog(accountId);
  const [editing, setEditing] = useState(false);
  const [catalogId, setCatalogId] = useState("");
  const [token, setToken] = useState("");
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(() =>
    arrival.error
      ? translateOr(t, `metaCatalog.errors.${arrival.error}`, t("metaCatalog.errors.refused"))
      : null,
  );
  const [notice, setNotice] = useState<string | null>(() =>
    arrival.connected ? t("metaCatalog.connectedNotice") : null,
  );

  useEffect(() => {
    if (arrival.pick || arrival.error || arrival.connected) router.replace(pathname);
  }, [arrival, router, pathname]);

  async function loginWithFacebook() {
    setError(null);
    setStarting(true);
    try {
      await startMetaCatalogLogin(accountId);
    } catch (err) {
      setError(errorText(err));
      setStarting(false);
    }
  }

  async function pick(id: string) {
    if (!nonce) return;
    setError(null);
    try {
      await choose.mutateAsync({ nonce, catalogId: id });
      setNonce(null);
      setNotice(t("metaCatalog.connectedNotice"));
    } catch (err) {
      setError(errorText(err));
    }
  }

  const picking = Boolean(nonce) && !pending.isError;
  const facebookButton = catalog.can_login ? (
    <Button type="button" size="sm" loading={starting} onClick={() => void loginWithFacebook()}>
      <Facebook mono className="h-4 w-4" aria-hidden />
      {t("metaCatalog.connectFacebook")}
    </Button>
  ) : null;

  function startEditing() {
    setCatalogId(catalog.connected ? catalog.catalog_id : "");
    setToken("");
    setError(null);
    setEditing(true);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await connect.mutateAsync({
        catalog_id: catalogId.trim(),
        ...(token.trim() ? { access_token: token.trim() } : {}),
      });
      setEditing(false);
      setToken("");
    } catch (err) {
      setError(errorText(err));
    }
  }

  async function runSync() {
    setError(null);
    setNotice(null);
    try {
      const res = await sync.mutateAsync();
      setNotice(t("metaCatalog.synced", res.result));
    } catch (err) {
      setError(errorText(err));
    }
  }

  async function unlink() {
    if (!(await confirm(t("metaCatalog.disconnectConfirm")))) return;
    setError(null);
    try {
      await disconnect.mutateAsync();
    } catch (err) {
      setError(errorText(err));
    }
  }

  const last = catalog.connected ? catalog.last_sync : null;
  const lastError = catalog.connected ? catalog.last_error : null;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <ShoppingBag className="h-4 w-4 text-fg-muted" aria-hidden />
          {t("metaCatalog.title")}
        </CardTitle>
        {catalog.connected && !editing && !picking ? (
          <span className="flex flex-wrap gap-1">
            <Button size="sm" onClick={() => void runSync()} loading={sync.isPending}>
              <RefreshCw className="h-4 w-4" aria-hidden />
              {t("metaCatalog.syncNow")}
            </Button>
            <Button size="sm" variant="ghost" onClick={startEditing}>
              {t("agenda.dialog.change")}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => void unlink()} disabled={disconnect.isPending}>
              {t("metaCatalog.disconnect")}
            </Button>
          </span>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-3">
        {error ? (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        ) : null}
        {notice ? (
          <p role="status" className="text-sm text-success">
            {notice}
          </p>
        ) : null}

        {nonce && pending.isError ? (
          <p role="alert" className="text-sm text-danger">
            {errorText(pending.error)}
          </p>
        ) : null}

        {picking ? (
          <div className="space-y-2">
            <p className="text-sm font-medium text-fg">{t("metaCatalog.whichCatalog")}</p>
            {pending.data?.map((row) => (
              <Button
                key={row.id}
                type="button"
                variant="simple"
                className="w-full justify-start"
                disabled={choose.isPending}
                onClick={() => void pick(row.id)}
              >
                <ShoppingBag className="h-4 w-4" aria-hidden />
                {row.name || t("metaCatalog.unnamed")}
                {row.business ? (
                  <span className="text-xs text-fg-muted">· {row.business}</span>
                ) : null}
              </Button>
            ))}
          </div>
        ) : editing ? (
          <form onSubmit={submit} className="space-y-3">
            {facebookButton ? (
              <div className="space-y-2 border-b border-glass pb-3">
                {facebookButton}
                <p className="text-xs text-fg-muted">{t("metaCatalog.orManual")}</p>
              </div>
            ) : null}
            <p className="text-sm text-fg-muted">{t("metaCatalog.howTo")}</p>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <Label htmlFor="meta-catalog-id">{t("metaCatalog.catalogId")}</Label>
                <Input
                  id="meta-catalog-id"
                  inputMode="numeric"
                  value={catalogId}
                  onChange={(e) => setCatalogId(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="meta-catalog-token">{t("metaCatalog.token")}</Label>
                <Input
                  id="meta-catalog-token"
                  type="password"
                  autoComplete="off"
                  value={token}
                  placeholder={catalog.connected ? t("metaCatalog.tokenKeep") : undefined}
                  onChange={(e) => setToken(e.target.value)}
                  required={!catalog.connected}
                />
              </div>
            </div>
            <div className="flex gap-2">
              <Button type="submit" size="sm" loading={connect.isPending}>
                {t("metaCatalog.connect")}
              </Button>
              <Button type="button" size="sm" variant="ghost" onClick={() => setEditing(false)}>
                {t("actions.cancel")}
              </Button>
            </div>
          </form>
        ) : catalog.connected ? (
          <div className="space-y-1 text-sm">
            <p className="font-medium text-fg">
              {catalog.catalog_name || t("metaCatalog.unnamed")}
              <span className="ml-2 font-numeric text-xs tabular-nums text-fg-muted">
                ID {catalog.catalog_id}
              </span>
            </p>
            <p className="text-fg-muted">
              {last
                ? t("metaCatalog.lastSync", {
                    date: new Date(last.at * 1000).toLocaleString(intlTag, {
                      dateStyle: "medium",
                      timeStyle: "short",
                    }),
                    sent: last.sent,
                    failed: last.failed + last.skipped,
                  })
                : t("metaCatalog.neverSynced")}
            </p>
            {lastError ? (
              <p role="alert" className="text-xs text-warning">
                {t("metaCatalog.lastError", {
                  error: translateOr(
                    t,
                    `metaCatalog.errors.${lastError.code}`,
                    t("metaCatalog.errors.refused"),
                  ),
                })}
              </p>
            ) : null}
            {catalog.login ? (
              <p className="text-xs text-fg-muted">
                {catalog.login.via === "facebook_business"
                  ? t("metaCatalog.viaBusiness")
                  : catalog.login.expires_at
                  ? t("metaCatalog.viaFacebookUntil", {
                      date: new Date(catalog.login.expires_at * 1000).toLocaleDateString(intlTag, {
                        dateStyle: "medium",
                      }),
                    })
                  : t("metaCatalog.viaFacebook")}
              </p>
            ) : null}
            {last && !last.validated ? (
              <p className="text-xs text-fg-muted">{t("metaCatalog.stillChecking")}</p>
            ) : null}
            <p className="text-xs text-fg-muted">{t("metaCatalog.autoSync")}</p>
          </div>
        ) : (
          <div className="space-y-2">
            <p className="text-sm text-fg-muted">{t("metaCatalog.intro")}</p>
            <div className="flex flex-wrap gap-2">
              {facebookButton}
              <Button
                size="sm"
                variant={facebookButton ? "ghost" : "secondary"}
                onClick={startEditing}
              >
                {facebookButton ? t("metaCatalog.pasteToken") : t("metaCatalog.connect")}
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/** One product's state in the catalogue, for its row in the list. */
export function useProductCatalogState() {
  const t = useT();
  return (product: {
    enabled: boolean;
    meta_sync?: boolean;
    meta_synced_at?: number | null;
    meta_sync_error?: string | null;
  }): { label: string; tone: "ok" | "warn" | "muted"; detail?: string } | null => {
    // Only the products chosen for the catalogue have a state there.
    if (!product.enabled || !product.meta_sync) return null;
    const err = product.meta_sync_error;
    if (err?.startsWith("missing:")) {
      const fields = err
        .slice(8)
        .split(",")
        .map((f) => translateOr(t, `metaCatalog.fields.${f}`, f))
        .join(", ");
      return { label: t("metaCatalog.state.missing", { fields }), tone: "warn" };
    }
    if (err) return { label: t("metaCatalog.state.refused"), tone: "warn", detail: err };
    if (product.meta_synced_at) return { label: t("metaCatalog.state.synced"), tone: "ok" };
    return { label: t("metaCatalog.state.pending"), tone: "muted" };
  };
}
