"use client";

import { UserPlus, X } from "lucide-react";
import { useState } from "react";

import { useAgents } from "@/lib/api/account";
import {
  useAddParticipant,
  useParticipants,
  useRemoveParticipant,
} from "@/lib/api/participants";

/**
 * The conversation's "watcher" set: agents who follow it for
 * notifications without being the assignee. Add via the picker (backend
 * rejects agents without inbox access with a 422 we surface), remove via
 * the chip's ✕.
 */
export function ConversationParticipants({
  accountId,
  displayId,
}: {
  accountId: string;
  displayId: number;
}) {
  const participants = useParticipants(accountId, displayId);
  const agents = useAgents(accountId);
  const add = useAddParticipant(accountId, displayId);
  const remove = useRemoveParticipant(accountId, displayId);
  const [error, setError] = useState<string | null>(null);

  const current = participants.data ?? [];
  const currentIds = new Set(current.map((p) => p.id));
  const addable = (agents.data ?? []).filter((a) => !currentIds.has(a.id));

  async function onAdd(userId: number) {
    setError(null);
    try {
      await add.mutateAsync(userId);
    } catch (e) {
      setError(
        (e as { message?: string })?.message ?? "No se pudo agregar.",
      );
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-border pb-3 pt-1">
      <span className="text-xs font-medium text-fg-muted">Participantes</span>

      {current.map((p) => (
        <span
          key={p.id}
          className="flex items-center gap-1 rounded-full border border-border bg-surface-2 px-2 py-0.5 text-xs text-fg"
        >
          {p.name}
          <button
            type="button"
            aria-label={`Quitar ${p.name}`}
            onClick={() => remove.mutate(p.id)}
            disabled={remove.isPending}
            className="rounded p-0.5 text-fg-muted hover:text-danger disabled:opacity-50"
          >
            <X className="h-3 w-3" aria-hidden />
          </button>
        </span>
      ))}

      {current.length === 0 ? (
        <span className="text-xs text-fg-muted">Nadie sigue esta conversación.</span>
      ) : null}

      {addable.length > 0 ? (
        <label className="flex items-center gap-1 text-xs text-fg-muted">
          <UserPlus className="h-3.5 w-3.5" aria-hidden />
          <select
            className="h-8 rounded-md border border-border bg-surface px-2 text-xs text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            value=""
            onChange={(e) => {
              const id = Number(e.target.value);
              if (id) onAdd(id);
              e.currentTarget.value = "";
            }}
            disabled={add.isPending}
            aria-label="Agregar participante"
          >
            <option value="">Agregar…</option>
            {addable.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      {error ? (
        <span role="alert" className="text-xs text-danger">
          {error}
        </span>
      ) : null}
    </div>
  );
}
