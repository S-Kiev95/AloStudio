import type { settingsMcp as es } from "../es/settingsMcp";
import type { Strings } from "../types";

export const settingsMcp: Strings<typeof es> = {
  rotateConfirm: "Das Token „{name}“ erneuern? Clients, die das aktuelle verwenden, schlagen sofort fehl.",
  deleteConfirm: "Das Token „{name}“ löschen?",
  lastUsed: "Zuletzt verwendet {when}",
  new: "Neues Token",
  intro: "Verwende diese Tokens, um dein Konto zu automatisieren und den KI-Agenten, n8n, die CLI oder andere externe Tools über die API und den MCP-Server mit AloStudio zu verbinden. Jedes Token ist diesem Konto mit Lese-, Schreib- oder Admin-Berechtigung zugeordnet.",
  edit: "Token bearbeiten",
  loadFailed: "Die Tokens konnten nicht geladen werden. Ist dein Konto ein Administrator?",
  empty: "Noch keine Tokens.",
  rotateFailed: "Erneuern nicht möglich.",
  neverUsed: "Nie verwendet",
  saveNow: "Jetzt speichern",
  shownOnce: "Dieses Token wird nur einmal angezeigt. Wenn du es verlierst, musst du es erneuern, um ein neues zu erzeugen.",
  copied: "Kopiert",
  copy: "Kopieren",
  saveFailed: "Das Token konnte nicht gespeichert werden.",
  namePlaceholder: "z. B. support-agent",
  permissions: "Berechtigungen",
  generate: "Token erzeugen",
};
