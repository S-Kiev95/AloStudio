import type { settingsInstall as es } from "../es/settingsInstall";
import type { Strings } from "../types";

export const settingsInstall: Strings<typeof es> = {
  configuredCount: "{done}/{total} configured",
  netConfigured: "configured",
  netNotConfigured: "not configured",
  operatorOnly: "Only the installation's operator can see this screen. Ask whoever deployed it for access.",
  loadFailed: "Couldn't load the configuration.",
  intro: "Settings that apply to all of AloStudio, not to one account. You can leave them empty and fill them in when you have the credentials — the app works without them, and each feature tells you what it's missing.",
  network: "Network",
  clearFailed: "Couldn't clear it.",
  notConfigured: "Not configured",
  configured: "Configured",
  savedHere: "saved from here",
  resetToServer: "go back to the server value",
  fromEnv: "comes from the server file (.env)",
};
