import type { oauth as es } from "../es/oauth";
import type { Strings } from "../types";

export const oauth: Strings<typeof es> = {
  scope: {
    readPosts: "Voir vos publications, canaux et statistiques",
    readConversations: "Voir les conversations et les contacts",
    writePosts: "Programmer et supprimer des publications",
    writeConversations: "Répondre aux conversations et les organiser",
  },
  cannotAuthorize: "Autorisation impossible",
  invalidRequest: "La demande de l’app n’est pas valide.",
  backToApp: "Retour à AloStudio",
  createdBy: "Créée par",
  willBeAbleTo: "Elle pourra :",
  whichAccount: "Sur quel compte ?",
  roleNotAllowed: "Votre rôle sur ce compte ne permet pas d’accorder cet accès",
  sendFailed: "Impossible d’envoyer votre réponse.",
  authorize: "Autoriser",
  wantsAccess: "{app} veut accéder à votre compte AloStudio",
  redirectNote: "Vous serez redirigé vers {host}. Vous pouvez retirer l’accès à tout moment dans Paramètres → Apps OAuth.",
};
