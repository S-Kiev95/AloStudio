"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type {
  AssignmentPolicy,
  AssignmentPolicyInput,
  ConversationPriority,
} from "@/lib/api/assignment-policies";

const selectClass =
  "h-11 w-full rounded-md border border-border bg-surface px-3 text-sm text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

const PRIORITY_LABELS: Record<ConversationPriority, string> = {
  earliest_created: "La creada primero",
  longest_waiting: "La que más espera",
};

export function AssignmentPolicyForm({
  initial,
  submitting,
  onSubmit,
  onCancel,
}: {
  initial?: AssignmentPolicy;
  submitting?: boolean;
  onSubmit: (input: AssignmentPolicyInput) => Promise<void> | void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [enabled, setEnabled] = useState(initial?.enabled ?? true);
  const [priority, setPriority] = useState<ConversationPriority>(
    initial?.conversation_priority ?? "earliest_created",
  );
  const [limit, setLimit] = useState(
    String(initial?.fair_distribution_limit ?? 100),
  );
  const [windowSecs, setWindowSecs] = useState(
    String(initial?.fair_distribution_window ?? 3600),
  );
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setError(null);
    if (!name.trim()) return setError("El nombre es obligatorio.");
    const limitNum = Number(limit);
    const windowNum = Number(windowSecs);
    if (!Number.isInteger(limitNum) || limitNum <= 0) {
      return setError("El límite debe ser un entero mayor que 0.");
    }
    if (!Number.isInteger(windowNum) || windowNum <= 0) {
      return setError("La ventana debe ser un entero mayor que 0.");
    }
    try {
      await onSubmit({
        name: name.trim(),
        description: description.trim() || null,
        enabled,
        conversation_priority: priority,
        fair_distribution_limit: limitNum,
        fair_distribution_window: windowNum,
      });
    } catch (e) {
      setError(
        (e as { message?: string })?.message ??
          "No se pudo guardar la política.",
      );
    }
  }

  return (
    <div className="space-y-4">
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}

      <div className="space-y-1.5">
        <Label htmlFor="ap-name" required>
          Nombre
        </Label>
        <Input
          id="ap-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Distribución equilibrada"
          maxLength={255}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="ap-description">Descripción</Label>
        <Textarea
          id="ap-description"
          rows={2}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Opcional"
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="ap-priority">Prioridad de conversación</Label>
        <select
          id="ap-priority"
          className={selectClass}
          value={priority}
          onChange={(e) =>
            setPriority(e.target.value as ConversationPriority)
          }
        >
          <option value="earliest_created">
            {PRIORITY_LABELS.earliest_created}
          </option>
          <option value="longest_waiting">
            {PRIORITY_LABELS.longest_waiting}
          </option>
        </select>
        <p className="text-xs text-fg-muted">
          Qué conversación en espera toma primero un agente disponible.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="ap-limit" required>
            Límite por agente
          </Label>
          <Input
            id="ap-limit"
            type="number"
            min={1}
            value={limit}
            onChange={(e) => setLimit(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="ap-window" required>
            Ventana (segundos)
          </Label>
          <Input
            id="ap-window"
            type="number"
            min={1}
            value={windowSecs}
            onChange={(e) => setWindowSecs(e.target.value)}
          />
        </div>
      </div>
      <p className="text-xs text-fg-muted">
        Se asignan como máximo <strong>{limit || "?"}</strong> conversaciones a
        cada agente cada <strong>{windowSecs || "?"}</strong> segundos.
      </p>

      <label className="flex items-center gap-2 text-sm text-fg">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => setEnabled(e.target.checked)}
          className="h-4 w-4 rounded border-border text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        Política activa
      </label>

      <div className="flex gap-2">
        <Button onClick={submit} loading={submitting}>
          {initial ? "Guardar cambios" : "Crear política"}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={submitting}>
          Cancelar
        </Button>
      </div>
    </div>
  );
}
