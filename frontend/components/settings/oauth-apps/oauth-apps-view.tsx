"use client";

import { AppWindow, Pencil, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  type OAuthApp,
  type OAuthAppInput,
  type OAuthEndpoints,
  useCreateOAuthApp,
  useDeleteOAuthApp,
  useOAuthApps,
  useRotateOAuthAppSecret,
  useUpdateOAuthApp,
} from "@/lib/api/oauth";
import { useIsAccountAdmin, useProfile } from "@/lib/api/profile";
import { cn } from "@/lib/utils";

import { AppForm } from "./app-form";
import { ApprovedApps } from "./approved-apps";
import { CopyField } from "./copy-field";
import { CredentialsReveal } from "./credentials-reveal";
import { useT } from "@/lib/i18n/provider";
import { rich } from "@/lib/i18n/rich";

type Revealed = { clientId: string; clientSecret?: string };

function errorMessage(e: unknown, fallback: string): string {
  return (e as { message?: string })?.message ?? fallback;
}

export function OAuthAppsView({ accountId }: { accountId: string }) {
  const t = useT();
  const profile = useProfile();
  const isAdmin = useIsAccountAdmin(accountId);
  const [tab, setTab] = useState<"apps" | "approved">("apps");
  // An agent only has "Apps aprobadas": registering apps is for admins.
  const current = isAdmin ? tab : "approved";

  if (profile.isLoading) {
    return (
      <div className="max-w-3xl space-y-4">
        <h2 className="text-xl font-medium text-fg">{t("settings.items.oauth_apps")}</h2>
        <p className="text-sm text-fg-muted">{t("common.loading")}</p>
      </div>
    );
  }

  return (
    <div className="max-w-3xl space-y-4">
      <h2 className="text-xl font-medium text-fg">{t("settings.items.oauth_apps")}</h2>
      <Tabs value={current} onValueChange={(v) => setTab(v as "apps" | "approved")}>
        <TabsList>
          {isAdmin ? <TabsTrigger value="apps">{t("settingsOauth.tabApps")}</TabsTrigger> : null}
          <TabsTrigger value="approved">{t("settingsOauth.tabApproved")}</TabsTrigger>
        </TabsList>
      </Tabs>
      {current === "apps" ? (
        <AppsPanel accountId={accountId} />
      ) : (
        <ApprovedApps accountId={accountId} />
      )}
    </div>
  );
}

function AppsPanel({ accountId }: { accountId: string }) {
  const t = useT();
  const { data, isLoading, isError } = useOAuthApps(accountId);
  const create = useCreateOAuthApp(accountId);
  const update = useUpdateOAuthApp(accountId);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<OAuthApp | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [revealed, setRevealed] = useState<Revealed | null>(null);

  async function handleCreate(input: OAuthAppInput) {
    setFormError(null);
    try {
      const app = await create.mutateAsync(input);
      setRevealed({ clientId: app.client_id, clientSecret: app.client_secret });
      setCreating(false);
    } catch (e) {
      setFormError(errorMessage(e, t("settingsOauth.createFailed")));
    }
  }

  async function handleUpdate(input: OAuthAppInput) {
    if (!editing) return;
    setFormError(null);
    try {
      await update.mutateAsync({
        id: editing.id,
        patch: { name: input.name, redirect_uris: input.redirect_uris },
      });
      setEditing(null);
    } catch (e) {
      setFormError(errorMessage(e, t("settingsOauth.saveFailed")));
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p className="max-w-xl text-sm text-fg-muted">
          {t("settingsOauth.intro")}
        </p>
        {!creating && !editing ? (
          <Button
            size="sm"
            onClick={() => {
              setFormError(null);
              setCreating(true);
            }}
          >
            <Plus className="h-4 w-4" aria-hidden />
            {t("settingsOauth.createApp")}
          </Button>
        ) : null}
      </div>

      {revealed ? (
        <CredentialsReveal
          clientId={revealed.clientId}
          clientSecret={revealed.clientSecret}
          onDismiss={() => setRevealed(null)}
        />
      ) : null}

      {creating || editing ? (
        <Card>
          <CardHeader>
            <CardTitle>{editing ? t("settingsOauth.editApp") : t("settingsOauth.newApp")}</CardTitle>
          </CardHeader>
          <CardContent>
            <AppForm
              key={editing?.id ?? "new"}
              initial={editing ?? undefined}
              submitting={create.isPending || update.isPending}
              error={formError}
              onSubmit={(input) =>
                void (editing ? handleUpdate(input) : handleCreate(input))
              }
              onCancel={() => {
                setCreating(false);
                setEditing(null);
                setFormError(null);
              }}
            />
          </CardContent>
        </Card>
      ) : null}

      <div className="overflow-hidden rounded-md border border-glass bg-surface">
        {isLoading ? (
          <p className="p-8 text-center text-sm text-fg-muted">{t("common.loading")}</p>
        ) : isError ? (
          <p role="alert" className="p-8 text-center text-sm text-danger">
            {t("settingsOauth.loadFailed")}
          </p>
        ) : (data?.apps.length ?? 0) === 0 ? (
          <p className="p-8 text-center text-sm text-fg-muted">
            {t("settingsOauth.empty")}
          </p>
        ) : (
          <ul className="divide-y divide-glass">
            {data?.apps.map((app) => (
              <AppRow
                key={app.id}
                accountId={accountId}
                app={app}
                onEdit={() => {
                  setCreating(false);
                  setFormError(null);
                  setEditing(app);
                }}
                onSecret={(secret) =>
                  setRevealed({ clientId: app.client_id, clientSecret: secret })
                }
              />
            ))}
          </ul>
        )}
      </div>

      {data ? <ConnectGuide endpoints={data.endpoints} /> : null}
    </div>
  );
}

function AppRow({
  accountId,
  app,
  onEdit,
  onSecret,
}: {
  accountId: string;
  app: OAuthApp;
  onEdit: () => void;
  onSecret: (secret: string) => void;
}) {
  const t = useT();
  const rotate = useRotateOAuthAppSecret(accountId);
  const del = useDeleteOAuthApp(accountId);
  const [error, setError] = useState<string | null>(null);

  async function onRotate() {
    if (
      !window.confirm(
        t("settingsOauth.rotateConfirm", { name: app.name }),
      )
    )
      return;
    setError(null);
    try {
      const rotated = await rotate.mutateAsync(app.id);
      if (rotated.client_secret) onSecret(rotated.client_secret);
    } catch (e) {
      setError(errorMessage(e, t("settingsOauth.rotateFailed")));
    }
  }

  async function onDelete() {
    if (
      !window.confirm(
        t("settingsOauth.deleteConfirm", { name: app.name }),
      )
    )
      return;
    setError(null);
    try {
      await del.mutateAsync(app.id);
    } catch (e) {
      setError(errorMessage(e, t("settingsOauth.deleteFailed")));
    }
  }

  const count = app.authorizations_count;

  return (
    <li className="space-y-3 px-4 py-3">
      <div className="flex items-center gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-focused text-lit">
          <AppWindow className="h-4 w-4" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-fg">{app.name}</p>
          <p className="text-xs text-fg-muted">
            {count === 0
              ? t("settingsOauth.noAuthorizations")
              : t(
                  count === 1
                    ? "settingsOauth.authorizationsOne"
                    : "settingsOauth.authorizationsMany",
                  { count },
                )}
          </p>
        </div>
        <span
          className={cn(
            "rounded-sm border px-2 py-0.5 text-xs font-medium",
            app.confidential
              ? "border-glass bg-focused text-lit"
              : "border-warning bg-surface-2 text-warning",
          )}
        >
          {app.confidential ? t("settingsOauth.confidential") : t("settingsOauth.public")}
        </span>
        {app.confidential ? (
          <button
            type="button"
            aria-label={t("settingsOauth.rotateSecretOf", { name: app.name })}
            title={t("settingsOauth.rotateSecret")}
            onClick={() => void onRotate()}
            disabled={rotate.isPending}
            className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 hover:text-fg disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <RefreshCw className="h-4 w-4" aria-hidden />
          </button>
        ) : null}
        <button
          type="button"
          aria-label={t("settingsOauth.editOf", { name: app.name })}
          title={t("actions.edit")}
          onClick={onEdit}
          className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Pencil className="h-4 w-4" aria-hidden />
        </button>
        <button
          type="button"
          aria-label={t("settingsOauth.deleteOf", { name: app.name })}
          title={t("settingsOauth.delete")}
          onClick={() => void onDelete()}
          disabled={del.isPending}
          className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 hover:text-danger disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Trash2 className="h-4 w-4" aria-hidden />
        </button>
      </div>
      <div className="grid gap-3 pl-12 sm:grid-cols-2">
        <CopyField label="Client ID" value={app.client_id} /> {/* i18n-ignore */}
        <div className="min-w-0 space-y-1">
          <p className="text-xs font-medium uppercase text-fg-muted">{t("settingsOauth.redirectUrl")}</p>
          {app.redirect_uris.map((uri) => (
            <p key={uri} className="truncate font-numeric text-xs text-fg">
              {uri}
            </p>
          ))}
        </div>
      </div>
      {error ? (
        <p role="alert" className="pl-12 text-xs text-danger">
          {error}
        </p>
      ) : null}
    </li>
  );
}

/** How a developer connects an app ("Docs" in the old screen). */
function ConnectGuide({ endpoints }: { endpoints: OAuthEndpoints }) {
  const t = useT();
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("settingsOauth.howTo")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <ol className="list-decimal space-y-1 pl-5 text-sm text-fg-muted">
          {/* i18n-ignore-start: protocol names stay as they are */}
          <li>
            {rich(t("settingsOauth.step1"), {
              client_id: <code>client_id</code>,
              redirect_uri: <code>redirect_uri</code>,
              scope: <code>scope</code>,
              read: <code>read</code>,
              write: <code>write</code>,
              state: <code>state</code>,
              code_challenge: <code>code_challenge</code>,
              S256: <code>S256</code>,
            })}
          </li>
          <li>
            {rich(t("settingsOauth.step2"), {
              code: <code>code</code>,
              code_verifier: <code>code_verifier</code>,
            })}
          </li>
          <li>
            {rich(t("settingsOauth.step3"), {
              header: <code>Authorization: Bearer</code>,
            })}
          </li>
          {/* i18n-ignore-end */}
        </ol>
        <div className="grid gap-3 sm:grid-cols-2">
          <CopyField label={t("settingsOauth.ep.authorization")} value={endpoints.authorization} />
          <CopyField label={t("settingsOauth.ep.token")} value={endpoints.token} />
          <CopyField label={t("settingsOauth.ep.revocation")} value={endpoints.revocation} />
          <CopyField label={t("settingsOauth.ep.mcp")} value={endpoints.mcp} />
          <CopyField label={t("settingsOauth.ep.metadata")} value={endpoints.metadata} />
        </div>
      </CardContent>
    </Card>
  );
}
