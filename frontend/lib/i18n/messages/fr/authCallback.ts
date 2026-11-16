import type { authCallback as es } from "../es/authCallback";
import type { Strings } from "../types";

export const authCallback: Strings<typeof es> = {
  googleCancelled: "La connexion avec Google a été annulée.",
  googleFailed: "Connexion avec Google impossible.",
  googleTitle: "Connexion avec Google",
  signingIn: "Connexion…",
  ssoNoToken: "Le lien d’accès ne contient pas de jeton.",
  ssoFailed: "Connexion impossible. Le lien a peut-être expiré.",
  ssoTitle: "Accès depuis Postiz",
};
