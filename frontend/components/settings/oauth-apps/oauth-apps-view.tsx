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

type Revealed = { clientId: string; clientSecret?: string };

function errorMessage(e: unknown, fallback: string): string {
  return (e as { message?: string })?.message ?? fallback;
}

export function OAuthAppsView({ accountId }: { accountId: string }) {
  const profile = useProfile();
  const isAdmin = useIsAccountAdmin(accountId);
  const [tab, setTab] = useState<"apps" | "approved">("apps");
  // An agent only has "Apps aprobadas": registering apps is for admins.
  const current = isAdmin ? tab : "approved";

  if (profile.isLoading) {
    return (
      <div className="max-w-3xl space-y-4">
        <h2 className="text-xl font-medium text-fg">Apps OAuth</h2>
        <p className="text-sm text-fg-muted">Cargando…</p>
      </div>
    );
  }

  return (
    <div className="max-w-3xl space-y-4">
      <h2 className="text-xl font-medium text-fg">Apps OAuth</h2>
      <Tabs value={current} onValueChange={(v) => setTab(v as "apps" | "approved")}>
        <TabsList>
          {isAdmin ? <TabsTrigger value="apps">Apps</TabsTrigger> : null}
          <TabsTrigger value="approved">Apps aprobadas</TabsTrigger>
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
      setFormError(errorMessage(e, "No se pudo crear la app."));
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
      setFormError(errorMessage(e, "No se pudo guardar la app."));
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p className="max-w-xl text-sm text-fg-muted">
          Registrá una app para que otros usuarios de AloStudio la autoricen
          sobre sus cuentas. La app recibe un token que funciona en el servidor
          MCP de AloStudio, igual que uno de “API y MCP”.
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
            Crear app OAuth
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
            <CardTitle>{editing ? "Editar app" : "Nueva app OAuth"}</CardTitle>
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
          <p className="p-8 text-center text-sm text-fg-muted">Cargando…</p>
        ) : isError ? (
          <p role="alert" className="p-8 text-center text-sm text-danger">
            No se pudieron cargar las apps.
          </p>
        ) : (data?.apps.length ?? 0) === 0 ? (
          <p className="p-8 text-center text-sm text-fg-muted">
            Todavía no registraste ninguna app.
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
  const rotate = useRotateOAuthAppSecret(accountId);
  const del = useDeleteOAuthApp(accountId);
  const [error, setError] = useState<string | null>(null);

  async function onRotate() {
    if (
      !window.confirm(
        `¿Regenerar el secreto de "${app.name}"? La app va a fallar hasta que cargue el nuevo.`,
      )
    )
      return;
    setError(null);
    try {
      const rotated = await rotate.mutateAsync(app.id);
      if (rotated.client_secret) onSecret(rotated.client_secret);
    } catch (e) {
      setError(errorMessage(e, "No se pudo regenerar el secreto."));
    }
  }

  async function onDelete() {
    if (
      !window.confirm(
        `¿Borrar la app "${app.name}"? Todos los que la autorizaron pierden el acceso.`,
      )
    )
      return;
    setError(null);
    try {
      await del.mutateAsync(app.id);
    } catch (e) {
      setError(errorMessage(e, "No se pudo borrar la app."));
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
              ? "Nadie la autorizó todavía"
              : count === 1
                ? "1 autorización"
                : `${count} autorizaciones`}
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
          {app.confidential ? "Confidencial" : "Pública"}
        </span>
        {app.confidential ? (
          <button
            type="button"
            aria-label={`Regenerar secreto de ${app.name}`}
            title="Regenerar secreto"
            onClick={() => void onRotate()}
            disabled={rotate.isPending}
            className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 hover:text-fg disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <RefreshCw className="h-4 w-4" aria-hidden />
          </button>
        ) : null}
        <button
          type="button"
          aria-label={`Editar ${app.name}`}
          title="Editar"
          onClick={onEdit}
          className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Pencil className="h-4 w-4" aria-hidden />
        </button>
        <button
          type="button"
          aria-label={`Borrar ${app.name}`}
          title="Borrar"
          onClick={() => void onDelete()}
          disabled={del.isPending}
          className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 hover:text-danger disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Trash2 className="h-4 w-4" aria-hidden />
        </button>
      </div>
      <div className="grid gap-3 pl-12 sm:grid-cols-2">
        <CopyField label="Client ID" value={app.client_id} />
        <div className="min-w-0 space-y-1">
          <p className="text-xs font-medium uppercase text-fg-muted">URL de retorno</p>
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
  return (
    <Card>
      <CardHeader>
        <CardTitle>Cómo conectar tu app</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <ol className="list-decimal space-y-1 pl-5 text-sm text-fg-muted">
          <li>
            Mandá al usuario a la URL de autorización con <code>client_id</code>,{" "}
            <code>redirect_uri</code>, <code>scope</code> (<code>read</code> o{" "}
            <code>write</code>), <code>state</code> y PKCE (
            <code>code_challenge</code> con <code>S256</code>).
          </li>
          <li>
            Cuando vuelve con <code>code</code>, cambialo por un token en la URL
            de token (con el secreto, o con <code>code_verifier</code> si es
            pública).
          </li>
          <li>
            Llamá al servidor MCP con <code>Authorization: Bearer</code> y el
            token. Dura una hora; renovalo con el refresh token.
          </li>
        </ol>
        <div className="grid gap-3 sm:grid-cols-2">
          <CopyField label="Autorización" value={endpoints.authorization} />
          <CopyField label="Token" value={endpoints.token} />
          <CopyField label="Revocación" value={endpoints.revocation} />
          <CopyField label="Servidor MCP" value={endpoints.mcp} />
          <CopyField label="Metadatos" value={endpoints.metadata} />
        </div>
      </CardContent>
    </Card>
  );
}
