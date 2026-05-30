"use client";

import { KeyRound, Pencil, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  MCP_SCOPES,
  type MCPScope,
  type MCPTokenInfo,
  type MCPTokenUpdateInput,
  useCreateMCPToken,
  useDeleteMCPToken,
  useMCPTokens,
  useRotateMCPToken,
  useUpdateMCPToken,
} from "@/lib/api/mcp-tokens";
import { cn } from "@/lib/utils";

import { SecretReveal } from "./secret-reveal";
import { TokenForm, TokenInputAdapter } from "./token-form";

const SCOPE_LABEL: Record<MCPScope, string> = Object.fromEntries(
  MCP_SCOPES.map((s) => [s.value, s.label]),
) as Record<MCPScope, string>;

export function MCPTokensView({ accountId }: { accountId: string }) {
  const { data, isLoading, isError } = useMCPTokens(accountId);
  const create = useCreateMCPToken(accountId);
  const update = useUpdateMCPToken(accountId);

  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<MCPTokenInfo | null>(null);
  const [secretLabel, setSecretLabel] = useState<string | null>(null);
  const [secret, setSecret] = useState<string | null>(null);

  async function handleCreate(input: { name: string; scope: MCPScope }) {
    const minted = await create.mutateAsync(input);
    setSecret(minted.token);
    setSecretLabel(minted.name);
    setCreating(false);
  }

  async function handleUpdate(input: MCPTokenUpdateInput) {
    if (!editing) return;
    await update.mutateAsync({ id: editing.id, patch: input });
    setEditing(null);
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-fg">Tokens MCP</h2>
        {!creating && !editing ? (
          <Button size="sm" onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" aria-hidden />
            Nuevo token
          </Button>
        ) : null}
      </div>

      <p className="text-sm text-fg-muted">
        Estos tokens autentican agentes de IA contra el servidor MCP. Cada
        token está atado a esta cuenta y tiene un alcance (lectura, escritura
        o admin).
      </p>

      {secret ? (
        <SecretReveal
          token={secret}
          onDismiss={() => {
            setSecret(null);
            setSecretLabel(null);
          }}
        />
      ) : null}

      {creating ? (
        <Card>
          <CardHeader>
            <CardTitle>Nuevo token</CardTitle>
          </CardHeader>
          <CardContent>
            <TokenForm
              submitting={create.isPending}
              onSubmit={handleCreate}
              onCancel={() => setCreating(false)}
            />
          </CardContent>
        </Card>
      ) : null}

      {editing ? (
        <Card>
          <CardHeader>
            <CardTitle>Editar token</CardTitle>
          </CardHeader>
          <CardContent>
            <TokenInputAdapter
              initial={editing}
              submitting={update.isPending}
              onUpdate={handleUpdate}
              onCancel={() => setEditing(null)}
            />
          </CardContent>
        </Card>
      ) : null}

      <div className="overflow-hidden rounded-lg border border-border bg-surface">
        {isLoading ? (
          <p className="p-8 text-center text-sm text-fg-muted">Cargando…</p>
        ) : isError ? (
          <p role="alert" className="p-8 text-center text-sm text-danger">
            No se pudieron cargar los tokens. ¿Tu cuenta es de administrador?
          </p>
        ) : (data?.length ?? 0) === 0 ? (
          <p className="p-8 text-center text-sm text-fg-muted">
            No hay tokens todavía.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {data?.map((t) => (
              <TokenRow
                key={t.id}
                accountId={accountId}
                token={t}
                highlight={secretLabel === t.name}
                onEdit={() => {
                  setCreating(false);
                  setEditing(t);
                }}
                onSecret={(value) => {
                  setSecret(value);
                  setSecretLabel(t.name);
                }}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function TokenRow({
  accountId,
  token,
  highlight,
  onEdit,
  onSecret,
}: {
  accountId: string;
  token: MCPTokenInfo;
  highlight: boolean;
  onEdit: () => void;
  onSecret: (newSecret: string) => void;
}) {
  const rotate = useRotateMCPToken(accountId);
  const del = useDeleteMCPToken(accountId);
  const [error, setError] = useState<string | null>(null);

  async function onRotate() {
    if (
      !window.confirm(
        `¿Rotar el token "${token.name}"? Los clientes que usan el actual van a fallar inmediatamente.`,
      )
    )
      return;
    setError(null);
    try {
      const minted = await rotate.mutateAsync(token.id);
      onSecret(minted.token);
    } catch (e) {
      setError((e as { message?: string })?.message ?? "No se pudo rotar.");
    }
  }

  async function onDelete() {
    if (!window.confirm(`¿Eliminar el token "${token.name}"?`)) return;
    setError(null);
    try {
      await del.mutateAsync(token.id);
    } catch (e) {
      setError((e as { message?: string })?.message ?? "No se pudo eliminar.");
    }
  }

  const lastUsed = token.last_used_at
    ? `Usado por última vez ${new Date(token.last_used_at).toLocaleString()}`
    : "Nunca usado";

  return (
    <li
      className={cn(
        "flex items-center gap-3 px-4 py-3",
        highlight && "bg-warning/5",
      )}
    >
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
        <KeyRound className="h-4 w-4" aria-hidden />
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-fg">{token.name}</p>
        <p className="text-xs text-fg-muted">{lastUsed}</p>
        {error ? (
          <p role="alert" className="text-xs text-danger">
            {error}
          </p>
        ) : null}
      </div>
      <span
        className={cn(
          "rounded-full px-2 py-0.5 text-xs font-medium",
          token.scope === "admin"
            ? "bg-danger/10 text-danger"
            : token.scope === "write"
              ? "bg-warning/10 text-warning"
              : "bg-info/10 text-info",
        )}
      >
        {SCOPE_LABEL[token.scope]}
      </span>
      <button
        type="button"
        aria-label="Rotar secret"
        title="Rotar secret"
        onClick={onRotate}
        disabled={rotate.isPending}
        className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <RefreshCw className="h-4 w-4" aria-hidden />
      </button>
      <button
        type="button"
        aria-label="Editar"
        title="Editar"
        onClick={onEdit}
        className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Pencil className="h-4 w-4" aria-hidden />
      </button>
      <button
        type="button"
        aria-label="Eliminar"
        title="Eliminar"
        onClick={onDelete}
        disabled={del.isPending}
        className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 hover:text-danger disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Trash2 className="h-4 w-4" aria-hidden />
      </button>
    </li>
  );
}
