import type { googleCalendar as es } from "../es/googleCalendar";
import type { Strings } from "../types";

export const googleCalendar: Strings<typeof es> = {
  title: "Google Agenda",
  intro: "Vos rendez-vous de l’Agenda et vos tâches CRM datées apparaissent dans votre Google Agenda et se mettent à jour toutes les 5 minutes. Ils se modifient dans AloStudio.",
  connect: "Connecter Google Agenda",
  reconnect: "Reconnecter",
  disconnect: "Déconnecter",
  connectedAs: "Connecté en tant que {email}",
  lastSync: "dernière synchronisation : {when}",
  waiting: "la première synchronisation arrive dans quelques minutes",
  revoked: "Google ne donne plus accès à votre agenda. Reconnectez-le.",
  syncFailed: "La dernière synchronisation a échoué : {detail}",
  connecting: "Connexion de votre agenda…",
  back: "Revenir à AloStudio",
  problems: {
    unavailable: "Google n’est pas configuré sur cette installation.",
    state: "Le lien a expiré ou appartenait à quelqu’un d’autre. Réessayez.",
    exchange: "Google n’a pas accepté la connexion. Réessayez.",
    no_refresh_token: "Google n’a pas donné d’accès durable. Réessayez.",
    cancelled: "La connexion avec Google a été annulée.",
    failed: "Impossible de se connecter à Google.",
  },
};
