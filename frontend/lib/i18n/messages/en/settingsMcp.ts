import type { settingsMcp as es } from "../es/settingsMcp";
import type { Strings } from "../types";

export const settingsMcp: Strings<typeof es> = {
  rotateConfirm: "Rotate the token \"{name}\"? Clients using the current one will fail immediately.",
  deleteConfirm: "Delete the token \"{name}\"?",
  lastUsed: "Last used {when}",
  new: "New token",
  intro: "Use these tokens to automate your account and connect the AI agent, n8n, the CLI or other external tools to AloStudio through the API and the MCP server. Each token is tied to this account with read, write or admin scope.",
  edit: "Edit token",
  loadFailed: "Couldn't load the tokens. Is your account an administrator?",
  empty: "No tokens yet.",
  rotateFailed: "Couldn't rotate.",
  neverUsed: "Never used",
  saveNow: "Save it now",
  shownOnce: "This token is only shown once. If you lose it, you'll have to rotate it to generate a new one.",
  copied: "Copied",
  copy: "Copy",
  saveFailed: "Couldn't save the token.",
  namePlaceholder: "E.g. support-agent",
  permissions: "Permissions",
  generate: "Generate token",
};
