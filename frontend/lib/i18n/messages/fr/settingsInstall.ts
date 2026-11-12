import type { settingsInstall as es } from "../es/settingsInstall";
import type { Strings } from "../types";

export const settingsInstall: Strings<typeof es> = {
  configuredCount: "{done}/{total} configurés",
  netConfigured: "configuré",
  netNotConfigured: "non configuré",
  operatorOnly: "Seul l’opérateur de l’installation peut voir cet écran. Demandez l’accès à la personne qui l’a déployée.",
  loadFailed: "Impossible de charger la configuration.",
  intro: "Des paramètres valables pour tout AloStudio, pas pour un seul compte. Vous pouvez les laisser vides et les remplir quand vous aurez les identifiants — l’app fonctionne sans eux, et chaque fonction vous indique ce qui lui manque.",
  network: "Réseau",
  clearFailed: "Impossible d’effacer.",
  notConfigured: "Non configuré",
  configured: "Configuré",
  savedHere: "enregistré ici",
  resetToServer: "revenir à la valeur du serveur",
  fromEnv: "provient du fichier du serveur (.env)",
};
