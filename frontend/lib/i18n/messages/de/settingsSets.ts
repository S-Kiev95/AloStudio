import type { settingsSets as es } from "../es/settingsSets";
import type { Strings } from "../types";

export const settingsSets: Strings<typeof es> = {
  title: "Sets ({count})",
  channelsLabel: "Kanäle: {names}",
  deleteFailed: "Das Set konnte nicht gelöscht werden.",
  intro: "Verwalte deine Inhalts-Sets, um sie einfach in deinen Beiträgen wiederzuverwenden.",
  add: "Set hinzufügen",
  loadFailed: "Die Sets konnten nicht geladen werden.",
  empty: "Noch keine Sets gespeichert.",
  noChannels: "Keine Kanäle",
  edit: "Set bearbeiten",
  delete: "Set löschen",
};
