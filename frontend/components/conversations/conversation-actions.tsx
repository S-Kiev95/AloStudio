"use client";

import { Plus, Tag } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { selectClassName } from "@/components/ui/select";
import { useAgents, useLabels } from "@/lib/api/account";
import {
  type Priority,
  useAssignAgent,
  useAssignTeam,
  useSetLabels,
  useTogglePriority,
} from "@/lib/api/conversations";
import { useExecuteMacro, useMacros } from "@/lib/api/macros";
import { useTeams } from "@/lib/api/teams";
import { cn } from "@/lib/utils";

const PRIORITIES: Priority[] = ["none", "low", "medium", "high", "urgent"];
const PRIORITY_LABEL: Record<Priority, string> = {
  none: "Sin prioridad",
  low: "Baja",
  medium: "Media",
  high: "Alta",
  urgent: "Urgente",
};

const selectClass = selectClassName("sm");

/**
 * Compact actions bar for a conversation: assignee, team, "+ Etiqueta",
 * priority, and macros. Reads current values from the loaded conversation;
 * each control fires its mutation (which invalidates the conversation cache).
 */
export function ConversationActions({
  accountId,
  displayId,
  priority,
  assigneeId,
  teamId = null,
  labels,
}: {
  accountId: string;
  displayId: number;
  priority: string | null;
  assigneeId: number | null;
  teamId?: number | null;
  labels: string[];
}) {
  const agents = useAgents(accountId);
  const teams = useTeams(accountId);
  const accountLabels = useLabels(accountId);
  const setPriority = useTogglePriority(accountId, displayId);
  const assign = useAssignAgent(accountId, displayId);
  const assignTeam = useAssignTeam(accountId, displayId);
  const setLabels = useSetLabels(accountId, displayId);
  const macros = useMacros(accountId);
  const execMacro = useExecuteMacro(accountId);

  const [labelMenuOpen, setLabelMenuOpen] = useState(false);
  const labelWrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!labelMenuOpen) return;
    function onDocClick(e: MouseEvent) {
      if (
        labelWrapRef.current &&
        !labelWrapRef.current.contains(e.target as Node)
      ) {
        setLabelMenuOpen(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setLabelMenuOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      window.removeEventListener("keydown", onKey);
    };
  }, [labelMenuOpen]);

  const current = new Set(labels);
  const teamList = teams.data ?? [];

  function toggleLabel(title: string) {
    const next = new Set(current);
    if (next.has(title)) next.delete(title);
    else next.add(title);
    setLabels.mutate([...next]);
  }

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-glass px-4 py-2">
      <label className="flex items-center gap-1.5 text-xs text-fg-muted">
        Asignado
        <select
          className={selectClass}
          value={assigneeId ?? ""}
          onChange={(e) =>
            assign.mutate(e.target.value ? Number(e.target.value) : null)
          }
          disabled={assign.isPending || agents.isLoading}
          aria-label="Asignar agente"
        >
          <option value="">Sin asignar</option>
          {agents.data?.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
            </option>
          ))}
        </select>
      </label>

      <label className="flex items-center gap-1.5 text-xs text-fg-muted">
        Equipo
        <select
          className={selectClass}
          value={teamId ?? ""}
          onChange={(e) =>
            assignTeam.mutate(e.target.value ? Number(e.target.value) : null)
          }
          disabled={assignTeam.isPending || teams.isLoading}
          aria-label="Equipo"
        >
          <option value="">
            {teamList.length === 0 ? "Sin equipos" : "Sin equipo"}
          </option>
          {teamList.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </select>
      </label>

      {/* Active labels + "+ Etiqueta" picker */}
      <div ref={labelWrapRef} className="relative flex flex-wrap items-center gap-1.5">
        {labels.map((title) => (
          <button
            key={title}
            type="button"
            onClick={() => toggleLabel(title)}
            disabled={setLabels.isPending}
            title="Quitar etiqueta"
            className="inline-flex items-center gap-1 rounded-pill border border-neon bg-focused px-2.5 py-0.5 text-xs font-medium text-lit transition-colors hover:bg-hover-glass"
          >
            <Tag className="h-3 w-3" aria-hidden />
            {title}
          </button>
        ))}
        <button
          type="button"
          aria-expanded={labelMenuOpen}
          onClick={() => setLabelMenuOpen((o) => !o)}
          className="inline-flex items-center gap-1 rounded-pill border border-glass bg-field px-2.5 py-1 text-xs font-medium text-fg-muted transition-colors hover:bg-hover-glass hover:text-fg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon"
        >
          <Plus className="h-3 w-3" aria-hidden />
          Etiqueta
        </button>

        {labelMenuOpen ? (
          <div
            role="menu"
            aria-label="Etiquetas disponibles"
            className="absolute left-0 top-full z-20 mt-1 min-w-[11rem] rounded-md border border-glass bg-surface-2 p-1.5 shadow-menu"
          >
            {!accountLabels.data?.length ? (
              <p className="px-2 py-1.5 text-xs text-fg-muted">
                No hay etiquetas creadas.
              </p>
            ) : (
              <ul className="max-h-48 overflow-y-auto">
                {accountLabels.data.map((l) => {
                  const on = current.has(l.title);
                  return (
                    <li key={l.id}>
                      <button
                        type="button"
                        role="menuitemcheckbox"
                        aria-checked={on}
                        disabled={setLabels.isPending}
                        onClick={() => toggleLabel(l.title)}
                        className={cn(
                          "flex w-full items-center justify-between gap-2 rounded-sm px-2.5 py-1.5 text-left text-xs transition-colors",
                          on
                            ? "bg-focused font-medium text-lit"
                            : "text-fg hover:bg-hover-glass",
                        )}
                      >
                        <span className="truncate">{l.title}</span>
                        {on ? <span aria-hidden>✓</span> : null}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        ) : null}
      </div>

      <label className="ml-auto flex items-center gap-1.5 text-xs text-fg-muted">
        Prioridad
        <select
          className={selectClass}
          value={(priority as Priority) ?? "none"}
          onChange={(e) => setPriority.mutate(e.target.value as Priority)}
          disabled={setPriority.isPending}
          aria-label="Prioridad"
        >
          {PRIORITIES.map((p) => (
            <option key={p} value={p}>
              {PRIORITY_LABEL[p]}
            </option>
          ))}
        </select>
      </label>

      {macros.data?.length ? (
        <label className="flex items-center gap-1.5 text-xs text-fg-muted">
          Macro
          <select
            className={selectClass}
            value=""
            onChange={(e) => {
              const id = Number(e.target.value);
              if (!id) return;
              execMacro.mutate({ id, conversation_ids: [displayId] });
              e.currentTarget.value = "";
            }}
            disabled={execMacro.isPending}
            aria-label="Correr macro"
          >
            <option value="">Correr macro…</option>
            {macros.data.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
        </label>
      ) : null}
    </div>
  );
}
