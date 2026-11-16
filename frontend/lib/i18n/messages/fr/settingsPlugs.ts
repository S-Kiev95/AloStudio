import type { settingsPlugs as es } from "../es/settingsPlugs";
import type { Strings } from "../types";

export const settingsPlugs: Strings<typeof es> = {
  messageTooLong: "Le message dépasse le maximum de {max} caractères ({count}/{max}).",
  channelPlugs: "Plugs de {name}",
  whenLikes: "Quand il atteint {n} j’aime",
  channelRequired: "Choisissez un canal pour configurer le plug.",
  actionRequired: "Choisissez une action du catalogue.",
  thresholdMin: "Le seuil doit être d’au moins 1 j’aime.",
  messageRequired: "Écrivez le message pour cette action.",
  saveFailed: "Impossible d’enregistrer le plug.",
  updateFailed: "Impossible de mettre à jour le plug.",
  deleteFailed: "Impossible de supprimer le plug.",
  title: "Plugs",
  intro: "Exécutez des actions automatiques sur vos publications quand elles atteignent un seuil de j’aime.",
  loadFailed: "Impossible de charger les plugs.",
  connectThreads: "Connectez Threads pour utiliser les actions automatiques",
  noChannels: "Aucun canal connecté n’a d’action disponible dans le catalogue.",
  goToCalendar: "Aller au calendrier pour connecter des canaux",
  add: "Ajouter un plug",
  noneInChannel: "Aucune action automatique configurée sur ce canal.",
  edit: "Modifier le plug",
  delete: "Supprimer le plug",
  lastRuns: "Dernières exécutions",
  runOk: "OK",
  runFailed: "Échec",
  channel: "Canal",
  thresholdLabel: "Quand il atteint N j’aime",
  message: "Message",
  messagePlaceholder: "Écrivez la réponse automatique…",
  save: "Enregistrer le plug",
  kinds: {
    reply_after_likes: {
      label: "Répondre à N j’aime",
      description: "Quand un post atteint ce nombre de j’aime, votre message est publié en réponse à ce même post (par exemple, un lien ou une offre).",
    },
    repost_after_likes: {
      label: "Republier à N j’aime",
      description: "Quand un post atteint ce nombre de j’aime, il est republié sur votre profil pour que vos abonnés le revoient.",
    },
  },
};
