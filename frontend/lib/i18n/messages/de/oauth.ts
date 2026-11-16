import type { oauth as es } from "../es/oauth";
import type { Strings } from "../types";

export const oauth: Strings<typeof es> = {
  scope: {
    readPosts: "Deine Beiträge, Kanäle und Statistiken sehen",
    readConversations: "Konversationen und Kontakte sehen",
    writePosts: "Beiträge planen und löschen",
    writeConversations: "Konversationen beantworten und organisieren",
  },
  cannotAuthorize: "Autorisierung nicht möglich",
  invalidRequest: "Die Anfrage der App ist ungültig.",
  backToApp: "Zurück zu AloStudio",
  createdBy: "Erstellt von",
  willBeAbleTo: "Sie kann:",
  whichAccount: "Für welches Konto?",
  roleNotAllowed: "Deine Rolle in diesem Konto erlaubt es nicht, diesen Zugriff zu gewähren",
  sendFailed: "Deine Antwort konnte nicht gesendet werden.",
  authorize: "Autorisieren",
  wantsAccess: "{app} möchte auf dein AloStudio-Konto zugreifen",
  redirectNote: "Du wirst zu {host} weitergeleitet. Du kannst den Zugriff jederzeit unter Einstellungen → OAuth-Apps entziehen.",
};
