import type { settingsInstall as es } from "../es/settingsInstall";
import type { Strings } from "../types";

export const settingsInstall: Strings<typeof es> = {
  configuredCount: "{done}/{total} eingerichtet",
  netConfigured: "eingerichtet",
  netNotConfigured: "nicht eingerichtet",
  operatorOnly: "Nur der Betreiber der Installation kann diese Seite sehen. Bitte die Person, die sie bereitgestellt hat, um Zugang.",
  loadFailed: "Die Konfiguration konnte nicht geladen werden.",
  intro: "Einstellungen, die für ganz AloStudio gelten, nicht für ein Konto. Du kannst sie leer lassen und ausfüllen, sobald du die Zugangsdaten hast — die App funktioniert ohne sie, und jede Funktion sagt dir, was ihr fehlt.",
  network: "Netzwerk",
  clearFailed: "Löschen nicht möglich.",
  notConfigured: "Nicht eingerichtet",
  configured: "Eingerichtet",
  savedHere: "hier gespeichert",
  resetToServer: "auf den Serverwert zurücksetzen",
  fromEnv: "stammt aus der Serverdatei (.env)",
};
