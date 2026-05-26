"use client";

import { Plus, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  ATTRIBUTE_DISPLAY_TYPES,
  type AttributeDisplayType,
  type AttributeModel,
  type CustomAttribute,
  type CustomAttributeInput,
} from "@/lib/api/custom-attributes";
import { cn } from "@/lib/utils";

const selectClass =
  "h-11 w-full rounded-md border border-border bg-surface px-3 text-sm text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

export function CustomAttributeForm({
  initial,
  submitting,
  onSubmit,
  onCancel,
}: {
  initial?: CustomAttribute;
  submitting?: boolean;
  onSubmit: (input: CustomAttributeInput) => Promise<void> | void;
  onCancel: () => void;
}) {
  const [displayName, setDisplayName] = useState(
    initial?.attribute_display_name ?? "",
  );
  const [description, setDescription] = useState(
    initial?.attribute_description ?? "",
  );
  const [displayType, setDisplayType] = useState<AttributeDisplayType>(
    initial?.attribute_display_type ?? "text",
  );
  const [model, setModel] = useState<AttributeModel>(
    initial?.attribute_model ?? "conversation_attribute",
  );
  const [regex, setRegex] = useState(initial?.regex_pattern ?? "");
  const [regexCue, setRegexCue] = useState(initial?.regex_cue ?? "");
  const [values, setValues] = useState<string[]>(
    initial?.attribute_values ?? [],
  );
  const [newValue, setNewValue] = useState("");
  const [error, setError] = useState<string | null>(null);

  function addValue() {
    const v = newValue.trim();
    if (!v) return;
    if (values.includes(v)) return;
    setValues((prev) => [...prev, v]);
    setNewValue("");
  }

  async function submit() {
    setError(null);
    if (!displayName.trim())
      return setError("El nombre visible es obligatorio.");
    const input: CustomAttributeInput = {
      attribute_display_name: displayName.trim(),
      attribute_display_type: displayType,
      attribute_model: model,
      attribute_description: description.trim() || null,
      regex_pattern: regex.trim() || null,
      regex_cue: regexCue.trim() || null,
      attribute_values: displayType === "list" ? values : [],
    };
    try {
      await onSubmit(input);
    } catch (e) {
      setError(
        (e as { message?: string })?.message ?? "No se pudo guardar el atributo.",
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
        <Label htmlFor="ca-name" required>
          Nombre visible
        </Label>
        <Input
          id="ca-name"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
        />
        {initial?.attribute_key ? (
          <p className="text-xs text-fg-muted">
            Clave: <code>{initial.attribute_key}</code> (no editable)
          </p>
        ) : null}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="ca-type">Tipo</Label>
          <select
            id="ca-type"
            className={selectClass}
            value={displayType}
            onChange={(e) =>
              setDisplayType(e.target.value as AttributeDisplayType)
            }
          >
            {ATTRIBUTE_DISPLAY_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="ca-model">Aplica a</Label>
          <select
            id="ca-model"
            className={selectClass}
            value={model}
            onChange={(e) => setModel(e.target.value as AttributeModel)}
            disabled={Boolean(initial)}
          >
            <option value="conversation_attribute">Conversaciones</option>
            <option value="contact_attribute">Contactos</option>
          </select>
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="ca-desc">Descripción</Label>
        <Textarea
          id="ca-desc"
          rows={2}
          value={description ?? ""}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>

      {displayType === "text" ? (
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="ca-regex">Patrón (regex)</Label>
            <Input
              id="ca-regex"
              value={regex ?? ""}
              onChange={(e) => setRegex(e.target.value)}
              placeholder="^[A-Z]{3}-\d+$"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="ca-cue">Pista para el usuario</Label>
            <Input
              id="ca-cue"
              value={regexCue ?? ""}
              onChange={(e) => setRegexCue(e.target.value)}
              placeholder="Ej. ABC-1234"
            />
          </div>
        </div>
      ) : null}

      {displayType === "list" ? (
        <div className="space-y-2">
          <Label>Valores</Label>
          <div className="flex flex-wrap gap-1.5">
            {values.length === 0 ? (
              <p className="text-sm text-fg-muted">
                Todavía no hay valores en la lista.
              </p>
            ) : (
              values.map((v) => (
                <span
                  key={v}
                  className={cn(
                    "inline-flex items-center gap-1 rounded-full",
                    "bg-surface-2 px-2 py-0.5 text-xs text-fg",
                  )}
                >
                  {v}
                  <button
                    type="button"
                    aria-label={`Quitar ${v}`}
                    onClick={() =>
                      setValues((prev) => prev.filter((x) => x !== v))
                    }
                    className="rounded-full p-0.5 hover:text-danger"
                  >
                    <X className="h-3 w-3" aria-hidden />
                  </button>
                </span>
              ))
            )}
          </div>
          <div className="flex gap-2">
            <Input
              value={newValue}
              onChange={(e) => setNewValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  addValue();
                }
              }}
              placeholder="Nuevo valor"
            />
            <Button type="button" variant="secondary" onClick={addValue}>
              <Plus className="h-4 w-4" aria-hidden />
              Agregar
            </Button>
          </div>
        </div>
      ) : null}

      <div className="flex gap-2">
        <Button onClick={submit} loading={submitting}>
          {initial ? "Guardar cambios" : "Crear atributo"}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={submitting}>
          Cancelar
        </Button>
      </div>
    </div>
  );
}
