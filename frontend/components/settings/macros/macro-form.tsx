"use client";

import { Plus } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type {
  Macro,
  MacroActionName,
  MacroInput,
  MacroVisibility,
} from "@/lib/api/macros";

import {
  MacroActionRow,
  paramsToText,
  textToParams,
} from "./macro-action-row";

type ActionDraft = { action_name: MacroActionName; text: string };

export function MacroForm({
  initial,
  submitting,
  onSubmit,
  onCancel,
}: {
  initial?: Macro;
  submitting?: boolean;
  onSubmit: (input: MacroInput) => Promise<void> | void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [visibility, setVisibility] = useState<MacroVisibility>(
    initial?.visibility ?? "personal",
  );
  const [actions, setActions] = useState<ActionDraft[]>(
    (initial?.actions ?? []).map((a) => ({
      action_name: a.action_name,
      text: paramsToText(a.action_name, a.action_params),
    })),
  );
  const [error, setError] = useState<string | null>(null);

  function addAction() {
    setActions((prev) => [...prev, { action_name: "send_message", text: "" }]);
  }

  async function submit() {
    setError(null);
    if (!name.trim()) return setError("El nombre es obligatorio.");
    if (actions.length === 0)
      return setError("Agregá al menos una acción.");

    const input: MacroInput = {
      name: name.trim(),
      visibility,
      actions: actions.map((a) => ({
        action_name: a.action_name,
        action_params: textToParams(a.action_name, a.text),
      })),
    };

    try {
      await onSubmit(input);
    } catch (e) {
      setError(
        (e as { message?: string })?.message ?? "No se pudo guardar el macro.",
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
        <Label htmlFor="m-name" required>
          Nombre
        </Label>
        <Input
          id="m-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={255}
        />
      </div>

      <div className="space-y-1.5">
        <Label>Visibilidad</Label>
        <div className="flex gap-3 text-sm">
          <label className="flex items-center gap-1.5">
            <input
              type="radio"
              checked={visibility === "personal"}
              onChange={() => setVisibility("personal")}
            />
            Personal
          </label>
          <label className="flex items-center gap-1.5">
            <input
              type="radio"
              checked={visibility === "global"}
              onChange={() => setVisibility("global")}
            />
            Global (visible para toda la cuenta)
          </label>
        </div>
      </div>

      <div className="space-y-2">
        <Label>Acciones</Label>
        {actions.length === 0 ? (
          <p className="text-sm text-fg-muted">
            Agregá al menos una acción para definir qué hace el macro.
          </p>
        ) : (
          <div className="space-y-2">
            {actions.map((a, i) => (
              <MacroActionRow
                key={i}
                value={a}
                onChange={(next) =>
                  setActions((prev) =>
                    prev.map((x, j) => (j === i ? next : x)),
                  )
                }
                onRemove={() =>
                  setActions((prev) => prev.filter((_, j) => j !== i))
                }
              />
            ))}
          </div>
        )}
        <Button type="button" variant="ghost" size="sm" onClick={addAction}>
          <Plus className="h-4 w-4" aria-hidden />
          Agregar acción
        </Button>
      </div>

      <div className="flex gap-2">
        <Button onClick={submit} loading={submitting}>
          {initial ? "Guardar cambios" : "Crear macro"}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={submitting}>
          Cancelar
        </Button>
      </div>
    </div>
  );
}
