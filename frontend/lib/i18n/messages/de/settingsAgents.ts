import type { settingsAgents as es } from "../es/settingsAgents";
import type { Strings } from "../types";

export const settingsAgents: Strings<typeof es> = {
  nameEmailRequired: "Name und E-Mail sind Pflichtfelder.",
  inviteFailed: "Die Einladung konnte nicht gesendet werden.",
  invite: "Agent einladen",
  role: "Rolle",
  roles: {
    agent: "Agent",
    administrator: "Administrator",
  },
  inviteNote: "Die Person bekommt eine E-Mail mit einem Link, um ihr Passwort festzulegen.",
  sendInvite: "Einladung senden",
  loadFailed: "Die Agenten konnten nicht geladen werden.",
  empty: "In diesem Konto gibt es noch keine Agenten.",
  roleFailed: "Die Rolle konnte nicht geändert werden.",
  removeFromAccount: "Aus dem Konto entfernen",
  removeConfirm: "{name} aus dem Konto entfernen?",
  removeNamed: "{name} entfernen",
  invited: "Wir haben eine Einladung an {email} gesendet. Der Link verfällt, sobald das Passwort festgelegt ist.",
};
