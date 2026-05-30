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

export function TeamsView({ accountId }: { accountId: string }) {
  const { data, isLoading, isError } = useTeams(accountId);
  const create = useCreateTeam(accountId);

  const [creating, setCreating] = useState(false);

  async function handleCreate(input: TeamInput) {
    await create.mutateAsync(input);
    setCreating(false);
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-fg">Equipos</h2>
        {!creating ? (
          <Button size="sm" onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" aria-hidden />
            Nuevo equipo
          </Button>
        ) : null}
      </div>

      {creating ? (
        <Card>
          <CardHeader>
            <CardTitle>Nuevo equipo</CardTitle>
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

      <div className="overflow-hidden rounded-lg border border-border bg-surface">
        {isLoading ? (
          <p className="p-8 text-center text-sm text-fg-muted">Cargando…</p>
        ) : isError ? (
          <p role="alert" className="p-8 text-center text-sm text-danger">
            No se pudieron cargar los equipos.
          </p>
        ) : (data?.length ?? 0) === 0 ? (
          <p className="p-8 text-center text-sm text-fg-muted">
            No hay equipos todavía.
          </p>
        ) : (
          <ul className="divide-y divide-border">
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
  const del = useDeleteTeam(accountId);
  const [error, setError] = useState<string | null>(null);

  async function onDelete(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (!window.confirm(`¿Eliminar el equipo "${team.name}"?`)) return;
    setError(null);
    try {
      await del.mutateAsync(team.id);
    } catch (err) {
      setError((err as { message?: string })?.message ?? "No se pudo eliminar.");
    }
  }

  return (
    <li className="flex items-center gap-1 pr-2 hover:bg-surface-2">
      <Link
        href={`/accounts/${accountId}/settings/teams/${team.id}`}
        className="flex min-w-0 flex-1 items-center gap-3 px-4 py-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
      >
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
          <Users className="h-4 w-4" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-fg">
            {team.name}
            {team.is_member ? (
              <span className="ml-2 rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium uppercase text-primary">
                Sos miembro
              </span>
            ) : null}
          </p>
          {team.description ? (
            <p className="truncate text-xs text-fg-muted">{team.description}</p>
          ) : null}
          {!team.allow_auto_assign ? (
            <p className="text-xs text-fg-muted">Sin asignación automática</p>
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
        aria-label="Eliminar"
        title="Eliminar"
        onClick={onDelete}
        disabled={del.isPending}
        className="rounded-md p-1.5 text-fg-muted hover:bg-surface hover:text-danger disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Trash2 className="h-4 w-4" aria-hidden />
      </button>
      <ChevronRight className="h-4 w-4 shrink-0 text-fg-muted" aria-hidden />
    </li>
  );
}
