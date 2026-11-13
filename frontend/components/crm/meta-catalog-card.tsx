"use client";

import { RefreshCw, ShoppingBag } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { type MetaCatalog, useMetaCatalogActions } from "@/lib/api/crm";
import { useIntlTag, useT } from "@/lib/i18n/provider";
import { translateOr } from "@/lib/i18n/translate";

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

/** CRM → Productos: the Meta catalogue the products are sent to. */
export function MetaCatalogCard({
  accountId,
  catalog,
}: {
  accountId: string;
  catalog: MetaCatalog;
}) {
  const t = useT();
  const intlTag = useIntlTag();
  const errorText = useCatalogError();
  const { connect, disconnect, sync } = useMetaCatalogActions(accountId);
  const [editing, setEditing] = useState(false);
  const [catalogId, setCatalogId] = useState("");
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

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
    if (!window.confirm(t("metaCatalog.disconnectConfirm"))) return;
    setError(null);
    try {
      await disconnect.mutateAsync();
    } catch (err) {
      setError(errorText(err));
    }
  }

  const last = catalog.connected ? catalog.last_sync : null;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <ShoppingBag className="h-4 w-4 text-fg-muted" aria-hidden />
          {t("metaCatalog.title")}
        </CardTitle>
        {catalog.connected && !editing ? (
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

        {editing ? (
          <form onSubmit={submit} className="space-y-3">
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
            {last && !last.validated ? (
              <p className="text-xs text-fg-muted">{t("metaCatalog.stillChecking")}</p>
            ) : null}
            <p className="text-xs text-fg-muted">{t("metaCatalog.autoSync")}</p>
          </div>
        ) : (
          <div className="space-y-2">
            <p className="text-sm text-fg-muted">{t("metaCatalog.intro")}</p>
            <Button size="sm" variant="secondary" onClick={startEditing}>
              {t("metaCatalog.connect")}
            </Button>
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
    meta_synced_at?: number | null;
    meta_sync_error?: string | null;
  }): { label: string; tone: "ok" | "warn" | "muted"; detail?: string } | null => {
    if (!product.enabled) return null;
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
