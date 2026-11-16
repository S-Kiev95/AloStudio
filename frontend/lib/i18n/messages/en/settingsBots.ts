import type { settingsBots as es } from "../es/settingsBots";
import type { Strings } from "../types";

export const settingsBots: Strings<typeof es> = {
  deleteConfirm: "Delete the bot \"{name}\"?",
  saveFailed: "Couldn't save the bot.",
  outgoingUrl: "Outgoing URL",
  outgoingUrlHint: "The backend will send message events to this URL.",
  create: "Create bot",
  new: "New bot",
  edit: "Edit bot",
  loadFailed: "Couldn't load the bots.",
  empty: "No bots yet.",
  secret: "Secret:",
  rotateSecret: "Rotate secret",
  rotateFailed: "Couldn't rotate the secret.",
};
