import type { settingsBots as es } from "../es/settingsBots";
import type { Strings } from "../types";

export const settingsBots: Strings<typeof es> = {
  deleteConfirm: "Den Bot „{name}“ löschen?",
  saveFailed: "Der Bot konnte nicht gespeichert werden.",
  outgoingUrl: "Ausgehende URL",
  outgoingUrlHint: "Das Backend sendet die Nachrichtenereignisse an diese URL.",
  create: "Bot erstellen",
  new: "Neuer Bot",
  edit: "Bot bearbeiten",
  loadFailed: "Die Bots konnten nicht geladen werden.",
  empty: "Noch keine Bots.",
  secret: "Secret:",
  rotateSecret: "Secret erneuern",
  rotateFailed: "Das Secret konnte nicht erneuert werden.",
};
