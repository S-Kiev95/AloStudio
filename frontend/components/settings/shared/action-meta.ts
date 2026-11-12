/**
 * Shared metadata + helpers for the {action_name, action_params} editor used
 * by both Macros (F.9c) and Automation rules (F.9e). The backend's
 * action executor is the same for both surfaces — only the allow-list
 * differs (automation adds 3 extras).
 */
import type { MessageKey } from "@/lib/i18n/translate";

export type ActionKind = "none" | "text" | "list" | "enum";

export type ActionMeta = {
  label: MessageKey;
  kind: ActionKind;
  placeholder?: MessageKey;
  options?: readonly string[];
};

/** Superset covering both macros (16) and automation extras (+3). */
export const ACTION_META: Record<string, ActionMeta> = {
  // --- shared with macros ---------------------------------------------------
  send_message: {
    label: "settingsAutomation.actions.send_message",
    kind: "text",
    placeholder: "settingsAutomation.ph.messageText",
  },
  add_label: {
    label: "settingsAutomation.actions.add_label",
    kind: "list",
    placeholder: "settingsAutomation.ph.labels",
  },
  assign_team: {
    label: "settingsAutomation.actions.assign_team",
    kind: "text",
    placeholder: "settingsAutomation.ph.teamId",
  },
  assign_agent: {
    label: "settingsAutomation.actions.assign_agent",
    kind: "list",
    placeholder: "settingsAutomation.ph.agentIds",
  },
  mute_conversation: { label: "settingsAutomation.actions.mute_conversation", kind: "none" },
  change_status: {
    label: "settingsAutomation.actions.change_status",
    kind: "enum",
    options: ["open", "resolved", "pending", "snoozed"],
  },
  remove_label: {
    label: "settingsAutomation.actions.remove_label",
    kind: "list",
    placeholder: "settingsAutomation.ph.labels",
  },
  remove_assigned_agent: { label: "settingsAutomation.actions.remove_assigned_agent", kind: "none" },
  remove_assigned_team: { label: "settingsAutomation.actions.remove_assigned_team", kind: "none" },
  resolve_conversation: { label: "settingsAutomation.actions.resolve_conversation", kind: "none" },
  snooze_conversation: {
    label: "settingsAutomation.actions.snooze_conversation",
    kind: "enum",
    options: ["tomorrow", "next_week", "next_month"],
  },
  change_priority: {
    label: "settingsAutomation.actions.change_priority",
    kind: "enum",
    options: ["urgent", "high", "medium", "low", "null"],
  },
  send_email_transcript: {
    label: "settingsAutomation.actions.send_email_transcript",
    kind: "text",
    placeholder: "settingsAutomation.ph.email",
  },
  send_attachment: {
    label: "settingsAutomation.actions.send_attachment",
    kind: "text",
    placeholder: "settingsAutomation.ph.fileRef",
  },
  add_private_note: {
    label: "settingsAutomation.actions.add_private_note",
    kind: "text",
    placeholder: "settingsAutomation.ph.noteText",
  },
  send_webhook_event: {
    label: "settingsAutomation.actions.send_webhook_event",
    kind: "text",
    placeholder: "settingsAutomation.ph.url",
  },
  // --- automation-only extras ----------------------------------------------
  send_email_to_team: {
    label: "settingsAutomation.actions.send_email_to_team",
    kind: "text",
    placeholder: "settingsAutomation.ph.teamId",
  },
  open_conversation: { label: "settingsAutomation.actions.open_conversation", kind: "none" },
  pending_conversation: {
    label: "settingsAutomation.actions.pending_conversation",
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
