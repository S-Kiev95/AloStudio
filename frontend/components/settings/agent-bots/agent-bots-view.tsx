"use client";

import { Bot, KeyRound, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type AgentBot,
  type AgentBotInput,
  useAgentBots,
  useCreateAgentBot,
  useDeleteAgentBot,
  useResetBotSecret,
  useUpdateAgentBot,
} from "@/lib/api/agent-bots";

import { AgentBotForm } from "./agent-bot-form";
import { useT } from "@/lib/i18n/provider";

export function AgentBotsView({ accountId }: { accountId: string }) {
  const t = useT();
  const { data, isLoading, isError } = useAgentBots(accountId);
  const create = useCreateAgentBot(accountId);
  const update = useUpdateAgentBot(accountId);

  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<AgentBot | null>(null);

  async function handleCreate(input: AgentBotInput) {
    await create.mutateAsync(input);
    setCreating(false);
  }

  async function handleUpdate(input: AgentBotInput) {
    if (!editing) return;
    await update.mutateAsync({ id: editing.id, patch: input });
    setEditing(null);
  }

  return (
    <div className="max-w-3xl space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-medium text-fg">{t("settings.items.agent_bots")}</h2>
        {!creating && !editing ? (
          <Button size="sm" onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" aria-hidden />
            {t("settingsBots.new")}
          </Button>
        ) : null}
      </div>

      {creating ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("settingsBots.new")}</CardTitle>
          </CardHeader>
          <CardContent>
            <AgentBotForm
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
            <CardTitle>{t("settingsBots.edit")}</CardTitle>
          </CardHeader>
          <CardContent>
            <AgentBotForm
              initial={editing}
              submitting={update.isPending}
              onSubmit={handleUpdate}
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
            {t("settingsBots.loadFailed")}
          </p>
        ) : (data?.length ?? 0) === 0 ? (
          <p className="p-8 text-center text-sm text-fg-muted">
            {t("settingsBots.empty")}
          </p>
        ) : (
          <ul className="divide-y divide-glass">
            {data?.map((b) => (
              <BotRow
                key={b.id}
                accountId={accountId}
                bot={b}
                onEdit={() => {
                  setCreating(false);
                  setEditing(b);
                }}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function BotRow({
  accountId,
  bot,
  onEdit,
}: {
  accountId: string;
  bot: AgentBot;
  onEdit: () => void;
}) {
  const t = useT();
  const del = useDeleteAgentBot(accountId);
  const reset = useResetBotSecret(accountId);
  const [error, setError] = useState<string | null>(null);
  const [revealed, setRevealed] = useState<string | null>(null);

  async function run(fn: () => Promise<unknown>, fallback: string) {
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError((e as { message?: string })?.message ?? fallback);
    }
  }

  return (
    <li className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-hover-glass">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-focused text-lit">
        <Bot className="h-4 w-4" aria-hidden />
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-fg">
          {bot.name}
          {bot.system_bot ? (
            <span className="ml-2 rounded-sm bg-surface-2 px-1.5 py-0.5 text-[10px] font-medium uppercase text-fg-muted">
              {t("theme.system")}
            </span>
          ) : null}
        </p>
        {bot.description ? (
          <p className="truncate text-xs text-fg-muted">{bot.description}</p>
        ) : null}
        {bot.outgoing_url ? (
          <p className="truncate text-xs text-fg-muted">{bot.outgoing_url}</p>
        ) : null}
        {revealed ? (
          <p className="text-xs">
            <span className="text-fg-muted">{t("settingsBots.secret")} </span>
            <code className="text-fg">{revealed}</code>
          </p>
        ) : null}
        {error ? (
          <p role="alert" className="text-xs text-danger">
            {error}
          </p>
        ) : null}
      </div>
      {!bot.system_bot ? (
        <>
          <button
            type="button"
            aria-label={t("settingsBots.rotateSecret")}
            title={t("settingsBots.rotateSecret")}
            onClick={() =>
              run(async () => {
                const rotated = await reset.mutateAsync(bot.id);
                setRevealed(rotated.secret ?? null);
              }, t("settingsBots.rotateFailed"))
            }
            disabled={reset.isPending}
            className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 hover:text-fg disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <KeyRound className="h-4 w-4" aria-hidden />
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
            onClick={() => {
              if (!window.confirm(t("settingsBots.deleteConfirm", { name: bot.name }))) return;
              run(() => del.mutateAsync(bot.id), t("actions.deleteFailed"));
            }}
            disabled={del.isPending}
            className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 hover:text-danger disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Trash2 className="h-4 w-4" aria-hidden />
          </button>
        </>
      ) : null}
    </li>
  );
}
