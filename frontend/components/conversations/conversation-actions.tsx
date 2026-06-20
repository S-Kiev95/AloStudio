"use client";

import { useAgents, useLabels } from "@/lib/api/account";
import {
  type Priority,
  useAssignAgent,
  useSetLabels,
  useTogglePriority,
} from "@/lib/api/conversations";
import { cn } from "@/lib/utils";

const PRIORITIES: Priority[] = ["none", "low", "medium", "high", "urgent"];
const PRIORITY_LABEL: Record<Priority, string> = {
  none: "Sin prioridad",
  low: "Baja",
  medium: "Media",
  high: "Alta",
  urgent: "Urgente",
};

const selectClass = cn(
  "h-9 rounded-md border border-border bg-surface px-2 text-sm text-fg",
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
);

/**
 * Compact actions bar for a conversation: priority, assignee, labels.
 * Reads current values from the loaded conversation; each control fires
 * its mutation (which invalidates the conversation cache).
 */
export function ConversationActions({
  accountId,
  displayId,
  priority,
  assigneeId,
  labels,
}: {
  accountId: string;
  displayId: number;
  priority: string | null;
  assigneeId: number | null;
  labels: string[];
}) {
  const agents = useAgents(accountId);
  const accountLabels = useLabels(accountId);
  const setPriority = useTogglePriority(accountId, displayId);
  const assign = useAssignAgent(accountId, displayId);
  const setLabels = useSetLabels(accountId, displayId);

  const current = new Set(labels);

  function toggleLabel(title: string) {
    const next = new Set(current);
    if (next.has(title)) next.delete(title);
    else next.add(title);
    setLabels.mutate([...next]);
  }

  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-border pb-3 pt-1">
      <label className="flex items-center gap-1.5 text-xs text-fg-muted">
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

      {accountLabels.data?.length ? (
        <div className="flex flex-wrap items-center gap-1.5">
          {accountLabels.data.map((l) => {
            const on = current.has(l.title);
            return (
              <button
                key={l.id}
                type="button"
                onClick={() => toggleLabel(l.title)}
                disabled={setLabels.isPending}
                aria-pressed={on}
                className={cn(
                  "rounded-full border px-2 py-0.5 text-xs",
                  on
                    ? "border-primary bg-surface-2 font-semibold text-fg"
                    : "border-border text-fg-muted hover:bg-surface-2",
                )}
              >
                {l.title}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
