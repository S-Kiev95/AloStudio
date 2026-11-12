"use client";

import { ChevronRight, Plus, Trash2, Users } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type Team,
  type TeamInput,
  useCreateTeam,
  useDeleteTeam,
  useTeams,
} from "@/lib/api/teams";

import { TeamForm } from "./team-form";
import { useT } from "@/lib/i18n/provider";

export function TeamsView({ accountId }: { accountId: string }) {
  const t = useT();
  const { data, isLoading, isError } = useTeams(accountId);
  const create = useCreateTeam(accountId);

  const [creating, setCreating] = useState(false);

  async function handleCreate(input: TeamInput) {
    await create.mutateAsync(input);
    setCreating(false);
  }

  return (
    <div className="max-w-3xl space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-medium text-fg">{t("settings.items.teams")}</h2>
        {!creating ? (
          <Button size="sm" onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" aria-hidden />
            {t("settingsTeams.new")}
          </Button>
        ) : null}
      </div>

      {creating ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("settingsTeams.new")}</CardTitle>
          </CardHeader>
          <CardContent>
            <TeamForm
              submitting={create.isPending}
              onSubmit={handleCreate}
              onCancel={() => setCreating(false)}
            />
          </CardContent>
        </Card>
      ) : null}

      <div className="overflow-hidden rounded-md border border-glass bg-surface">
        {isLoading ? (
          <p className="p-8 text-center text-sm text-fg-muted">{t("common.loading")}</p>
        ) : isError ? (
          <p role="alert" className="p-8 text-center text-sm text-danger">
            {t("settingsTeams.listLoadFailed")}
          </p>
        ) : (data?.length ?? 0) === 0 ? (
          <p className="p-8 text-center text-sm text-fg-muted">
            {t("settingsTeams.empty")}
          </p>
        ) : (
          <ul className="divide-y divide-glass">
            {data?.map((t) => (
              <TeamRow key={t.id} accountId={accountId} team={t} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function TeamRow({ accountId, team }: { accountId: string; team: Team }) {
  const t = useT();
  const del = useDeleteTeam(accountId);
  const [error, setError] = useState<string | null>(null);

  async function onDelete(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (!window.confirm(t("settingsTeams.deleteConfirm", { name: team.name }))) return;
    setError(null);
    try {
      await del.mutateAsync(team.id);
    } catch (err) {
      setError((err as { message?: string })?.message ?? t("actions.deleteFailed"));
    }
  }

  return (
    <li className="flex items-center gap-1 pr-2 transition-colors hover:bg-hover-glass">
      <Link
        href={`/accounts/${accountId}/settings/teams/${team.id}`}
        className="flex min-w-0 flex-1 items-center gap-3 px-4 py-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
      >
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-focused text-lit">
          <Users className="h-4 w-4" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-fg">
            {team.name}
            {team.is_member ? (
              <span className="ml-2 rounded-sm bg-focused px-1.5 py-0.5 text-[10px] font-medium uppercase text-lit">
                {t("settingsTeams.youAreMember")}
              </span>
            ) : null}
          </p>
          {team.description ? (
            <p className="truncate text-xs text-fg-muted">{team.description}</p>
          ) : null}
          {!team.allow_auto_assign ? (
            <p className="text-xs text-fg-muted">{t("settingsTeams.noAutoAssign")}</p>
          ) : null}
          {error ? (
            <p role="alert" className="text-xs text-danger">
              {error}
            </p>
          ) : null}
        </div>
      </Link>
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
      <ChevronRight className="h-4 w-4 shrink-0 text-fg-muted" aria-hidden />
    </li>
  );
}
