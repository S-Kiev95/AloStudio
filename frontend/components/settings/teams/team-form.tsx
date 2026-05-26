"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { Team, TeamInput } from "@/lib/api/teams";

export function TeamForm({
  initial,
  submitting,
  onSubmit,
  onCancel,
  submitLabel,
}: {
  initial?: Team;
  submitting?: boolean;
  onSubmit: (input: TeamInput) => Promise<void> | void;
  onCancel: () => void;
  submitLabel?: string;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [allowAutoAssign, setAllowAutoAssign] = useState(
    initial?.allow_auto_assign ?? true,
  );
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setError(null);
    if (!name.trim()) return setError("El nombre es obligatorio.");
    try {
      await onSubmit({
        name: name.trim(),
        description: description.trim() || null,
        allow_auto_assign: allowAutoAssign,
      });
    } catch (e) {
      setError(
        (e as { message?: string })?.message ?? "No se pudo guardar el equipo.",
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
        <Label htmlFor="t-name" required>
          Nombre
        </Label>
        <Input
          id="t-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={255}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="t-desc">Descripción</Label>
        <Textarea
          id="t-desc"
          rows={2}
          value={description ?? ""}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>

      <label className="flex items-center gap-2 text-sm text-fg">
        <input
          type="checkbox"
          checked={allowAutoAssign}
          onChange={(e) => setAllowAutoAssign(e.target.checked)}
        />
        Permitir asignación automática
      </label>

      <div className="flex gap-2">
        <Button onClick={submit} loading={submitting}>
          {submitLabel ?? (initial ? "Guardar cambios" : "Crear equipo")}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={submitting}>
          Cancelar
        </Button>
      </div>
    </div>
  );
}
