"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { useAgents } from "@/lib/api/account";
import { ApiError } from "@/lib/api/errors";
import { useUpdateInbox } from "@/lib/api/inboxes";

/**
 * Default assignee for bot handoffs: when the AI hands a conversation to the
 * team and nobody is assigned yet, it goes to this person (who gets the
 * notice). "Nadie" leaves it unassigned and notifies the whole inbox.
 */
export function HandoffAssigneePanel({
  accountId,
  inboxId,
  current,
}: {
  accountId: string;
  inboxId: number;
  current: number | null;
}) {
  const agents = useAgents(accountId);
  const update = useUpdateInbox(accountId);
  const [value, setValue] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setValue(current ? String(current) : "");
  }, [current]);

  async function save() {
    setError(null);
    setSaved(false);
    try {
      await update.mutateAsync({
        id: inboxId,
        patch: { handoff_assignee_id: value ? Number(value) : 0 },
      });
      setSaved(true);
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message : "No se pudo guardar el responsable.",
      );
    }
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-fg-muted">
        Cuando la IA derive una conversación a una persona y todavía no esté
        asignada, se le asigna a quien elijas y le llega el aviso. Con
        &quot;Nadie&quot;, el aviso le llega a todos los agentes de la bandeja.
      </p>
      <label className="block space-y-1">
        <span className="text-sm font-medium text-fg">Responsable</span>
        <Select
          value={value}
          disabled={agents.isLoading}
          onChange={(e) => {
            setValue(e.target.value);
            setSaved(false);
          }}
          className="max-w-xs"
        >
          <option value="">Nadie</option>
          {(agents.data ?? []).map((a) => (
            <option key={a.id} value={String(a.id)}>
              {a.available_name || a.name}
            </option>
          ))}
        </Select>
      </label>
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}
      <div className="flex items-center gap-2">
        <Button size="sm" onClick={save} loading={update.isPending}>
          Guardar
        </Button>
        {saved ? <span className="text-xs text-success">Guardado ✓</span> : null}
      </div>
    </div>
  );
}
