import type { settingsTeams as es } from "../es/settingsTeams";
import type { Strings } from "../types";

export const settingsTeams: Strings<typeof es> = {
  back: "Zurück zu den Teams",
  loadFailed: "Das Team konnte nicht geladen werden.",
  saveFailed: "Das Team konnte nicht gespeichert werden.",
  autoAssign: "Automatische Zuweisung erlauben",
  create: "Team erstellen",
  addMemberFailed: "Das Mitglied konnte nicht hinzugefügt werden.",
  removeMemberFailed: "Das Mitglied konnte nicht entfernt werden.",
  members: "Mitglieder",
  addMember: "Mitglied hinzufügen",
  availableAgents: "Verfügbare Agenten",
  allMembers: "Alle Agenten sind bereits Mitglieder dieses Teams.",
  loadingMembers: "Mitglieder werden geladen…",
  membersLoadFailed: "Die Mitglieder konnten nicht geladen werden.",
  noMembers: "Das Team hat keine Mitglieder.",
  removeFromTeam: "Aus dem Team entfernen",
  new: "Neues Team",
  listLoadFailed: "Die Teams konnten nicht geladen werden.",
  empty: "Noch keine Teams.",
  youAreMember: "Du bist Mitglied",
  noAutoAssign: "Keine automatische Zuweisung",
  deleteConfirm: "Das Team „{name}“ löschen?",
  removeConfirm: "{name} aus dem Team entfernen?",
};
