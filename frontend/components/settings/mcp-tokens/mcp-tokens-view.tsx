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
import { useIntlTag, useT } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/translate";

const SCOPE_LABEL: Record<MCPScope, MessageKey> = Object.fromEntries(
  MCP_SCOPES.map((s) => [s.value, s.label]),
) as Record<MCPScope, MessageKey>;

export function MCPTokensView({ accountId }: { accountId: string }) {
  const t = useT();
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
    <div className="max-w-3xl space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-medium text-fg">{t("settings.items.mcp_tokens")}</h2>
        {!creating && !editing ? (
          <Button size="sm" onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" aria-hidden />
            {t("settingsMcp.new")}
          </Button>
        ) : null}
      </div>

      <p className="text-sm text-fg-muted">
        {t("settingsMcp.intro")}
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
            <CardTitle>{t("settingsMcp.new")}</CardTitle>
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
            <CardTitle>{t("settingsMcp.edit")}</CardTitle>
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

      <div className="overflow-hidden rounded-md border border-glass bg-surface">
        {isLoading ? (
          <p className="p-8 text-center text-sm text-fg-muted">{t("common.loading")}</p>
        ) : isError ? (
          <p role="alert" className="p-8 text-center text-sm text-danger">
            {t("settingsMcp.loadFailed")}
          </p>
        ) : (data?.length ?? 0) === 0 ? (
          <p className="p-8 text-center text-sm text-fg-muted">
            {t("settingsMcp.empty")}
          </p>
        ) : (
          <ul className="divide-y divide-glass">
            {data?.map((tok) => (
              <TokenRow
                key={tok.id}
                accountId={accountId}
                token={tok}
                highlight={secretLabel === tok.name}
                onEdit={() => {
                  setCreating(false);
                  setEditing(tok);
                }}
                onSecret={(value) => {
                  setSecret(value);
                  setSecretLabel(tok.name);
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
  const t = useT();
  const intlTag = useIntlTag();
  const rotate = useRotateMCPToken(accountId);
  const del = useDeleteMCPToken(accountId);
  const [error, setError] = useState<string | null>(null);

  async function onRotate() {
    if (
      !window.confirm(
        t("settingsMcp.rotateConfirm", { name: token.name }),
      )
    )
      return;
    setError(null);
    try {
      const minted = await rotate.mutateAsync(token.id);
      onSecret(minted.token);
    } catch (e) {
      setError((e as { message?: string })?.message ?? t("settingsMcp.rotateFailed"));
    }
  }

  async function onDelete() {
    if (!window.confirm(t("settingsMcp.deleteConfirm", { name: token.name }))) return;
    setError(null);
    try {
      await del.mutateAsync(token.id);
    } catch (e) {
      setError((e as { message?: string })?.message ?? t("actions.deleteFailed"));
    }
  }

  const lastUsed = token.last_used_at
    ? t("settingsMcp.lastUsed", { when: new Date(token.last_used_at).toLocaleString(intlTag) })
    : t("settingsMcp.neverUsed");

  return (
    <li
      className={cn(
        "flex items-center gap-3 px-4 py-3 transition-colors hover:bg-hover-glass",
        highlight && "bg-focused",
      )}
    >
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-focused text-lit">
        <KeyRound className="h-4 w-4" aria-hidden />
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-fg">{token.name}</p>
        <p className="font-numeric text-xs tabular-nums text-fg-muted">{lastUsed}</p>
        {error ? (
          <p role="alert" className="text-xs text-danger">
            {error}
          </p>
        ) : null}
      </div>
      <span
        className={cn(
          "rounded-sm border px-2 py-0.5 text-xs font-medium",
          token.scope === "admin"
            ? "border-danger bg-surface-2 text-danger"
            : token.scope === "write"
              ? "border-warning bg-surface-2 text-warning"
              : "border-glass bg-focused text-lit",
        )}
      >
        {t(SCOPE_LABEL[token.scope])}
      </span>
      <button
        type="button"
        aria-label={t("settingsBots.rotateSecret")}
        title={t("settingsBots.rotateSecret")}
        onClick={onRotate}
        disabled={rotate.isPending}
        className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 hover:text-fg disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <RefreshCw className="h-4 w-4" aria-hidden />
      </button>
      <button
        type="button"
        aria-label={t("actions.edit")}
        title={t("actions.edit")}
        onClick={onEdit}
        className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Pencil className="h-4 w-4" aria-hidden />
      </button>
      <button
        type="button"
        aria-label={t("actions.delete")}
        title={t("actions.delete")}
        onClick={onDelete}
        disabled={del.isPending}
        className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 hover:text-danger disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Trash2 className="h-4 w-4" aria-hidden />
      </button>
    </li>
  );
}
