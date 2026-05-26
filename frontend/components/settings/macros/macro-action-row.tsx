"use client";

import { Trash2 } from "lucide-react";

import { Input } from "@/components/ui/input";
import { MACRO_ACTIONS, type MacroActionName } from "@/lib/api/macros";

/** Per-action metadata: label, input kind, and (for enums) allowed values. */
type ActionKind = "none" | "text" | "list" | "enum";
type ActionMeta = {
  label: string;
  kind: ActionKind;
  placeholder?: string;
  options?: readonly string[];
};

export const ACTION_META: Record<MacroActionName, ActionMeta> = {
  send_message: {
    label: "Enviar mensaje",
    kind: "text",
    placeholder: "Texto del mensaje",
  },
  add_label: {
    label: "Agregar etiqueta",
    kind: "list",
    placeholder: "etiqueta1, etiqueta2",
  },
  assign_team: {
    label: "Asignar equipo",
    kind: "text",
    placeholder: "ID del equipo",
  },
  assign_agent: {
    label: "Asignar agente",
    kind: "list",
    placeholder: "ID de agente (o varios separados por coma)",
  },
  mute_conversation: { label: "Silenciar conversación", kind: "none" },
  change_status: {
    label: "Cambiar estado",
    kind: "enum",
    options: ["open", "resolved", "pending", "snoozed"],
  },
  remove_label: {
    label: "Quitar etiqueta",
    kind: "list",
    placeholder: "etiqueta1, etiqueta2",
  },
  remove_assigned_agent: { label: "Quitar agente asignado", kind: "none" },
  remove_assigned_team: { label: "Quitar equipo asignado", kind: "none" },
  resolve_conversation: { label: "Resolver conversación", kind: "none" },
  snooze_conversation: {
    label: "Posponer conversación",
    kind: "enum",
    options: ["tomorrow", "next_week", "next_month"],
  },
  change_priority: {
    label: "Cambiar prioridad",
    kind: "enum",
    options: ["urgent", "high", "medium", "low", "null"],
  },
  send_email_transcript: {
    label: "Enviar transcripción por email",
    kind: "text",
    placeholder: "email@dominio",
  },
  send_attachment: {
    label: "Enviar archivo adjunto",
    kind: "text",
    placeholder: "URL o ID del archivo",
  },
  add_private_note: {
    label: "Agregar nota privada",
    kind: "text",
    placeholder: "Texto de la nota",
  },
  send_webhook_event: {
    label: "Disparar webhook",
    kind: "text",
    placeholder: "https://…",
  },
};

/** Convert the backend's ``action_params`` array into the editor's text value. */
export function paramsToText(
  actionName: MacroActionName,
  params: unknown[],
): string {
  const meta = ACTION_META[actionName];
  if (meta.kind === "none") return "";
  if (meta.kind === "list") return (params ?? []).map(String).join(", ");
  // text or enum — single value.
  const first = (params ?? [])[0];
  if (first === null) return "null";
  return first === undefined ? "" : String(first);
}

/** Inverse of {@link paramsToText}. Returns the ``action_params`` array. */
export function textToParams(
  actionName: MacroActionName,
  text: string,
): unknown[] {
  const meta = ACTION_META[actionName];
  if (meta.kind === "none") return [];
  if (meta.kind === "list")
    return text
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  // change_priority allows the literal string "null" (= clear priority).
  if (text === "null") return [null];
  return [text];
}

export function MacroActionRow({
  value,
  onChange,
  onRemove,
}: {
  value: { action_name: MacroActionName; text: string };
  onChange: (next: { action_name: MacroActionName; text: string }) => void;
  onRemove: () => void;
}) {
  const meta = ACTION_META[value.action_name];

  return (
    <div className="flex flex-wrap items-start gap-2 rounded-md border border-border bg-surface p-2">
      <select
        aria-label="Acción"
        value={value.action_name}
        onChange={(e) =>
          onChange({
            action_name: e.target.value as MacroActionName,
            text: "",
          })
        }
        className="h-9 rounded-md border border-border bg-surface px-2 text-sm text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {MACRO_ACTIONS.map((a) => (
          <option key={a} value={a}>
            {ACTION_META[a].label}
          </option>
        ))}
      </select>

      {meta.kind === "none" ? (
        <p className="self-center text-xs text-fg-muted">Sin parámetros</p>
      ) : meta.kind === "enum" ? (
        <select
          aria-label="Valor"
          value={value.text || (meta.options?.[0] ?? "")}
          onChange={(e) => onChange({ ...value, text: e.target.value })}
          className="h-9 min-w-32 flex-1 rounded-md border border-border bg-surface px-2 text-sm text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {meta.options?.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      ) : (
        <Input
          aria-label="Parámetros"
          value={value.text}
          onChange={(e) => onChange({ ...value, text: e.target.value })}
          placeholder={meta.placeholder}
          className="h-9 min-w-44 flex-1"
        />
      )}

      <button
        type="button"
        aria-label="Quitar acción"
        title="Quitar acción"
        onClick={onRemove}
        className="rounded-md p-2 text-fg-muted hover:bg-surface-2 hover:text-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Trash2 className="h-4 w-4" aria-hidden />
      </button>
    </div>
  );
}
