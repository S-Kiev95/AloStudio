/**
 * Shared metadata + helpers for the {action_name, action_params} editor used
 * by both Macros (F.9c) and Automation rules (F.9e). The backend's
 * action executor is the same for both surfaces — only the allow-list
 * differs (automation adds 3 extras).
 */
export type ActionKind = "none" | "text" | "list" | "enum";

export type ActionMeta = {
  label: string;
  kind: ActionKind;
  placeholder?: string;
  options?: readonly string[];
};

/** Superset covering both macros (16) and automation extras (+3). */
export const ACTION_META: Record<string, ActionMeta> = {
  // --- shared with macros ---------------------------------------------------
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
  // --- automation-only extras ----------------------------------------------
  send_email_to_team: {
    label: "Enviar email al equipo",
    kind: "text",
    placeholder: "ID del equipo",
  },
  open_conversation: { label: "Reabrir conversación", kind: "none" },
  pending_conversation: {
    label: "Marcar como pendiente",
    kind: "none",
  },
};

/** Convert backend ``action_params`` array → editor text. */
export function paramsToText(actionName: string, params: unknown[]): string {
  const meta = ACTION_META[actionName];
  if (!meta || meta.kind === "none") return "";
  if (meta.kind === "list") return (params ?? []).map(String).join(", ");
  const first = (params ?? [])[0];
  if (first === null) return "null";
  return first === undefined ? "" : String(first);
}

/** Inverse of {@link paramsToText}. */
export function textToParams(actionName: string, text: string): unknown[] {
  const meta = ACTION_META[actionName];
  if (!meta || meta.kind === "none") return [];
  if (meta.kind === "list")
    return text
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  // change_priority allows the literal "null" string (= clear priority).
  if (text === "null") return [null];
  return [text];
}
