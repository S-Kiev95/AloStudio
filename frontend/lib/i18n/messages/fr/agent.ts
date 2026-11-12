import type { agent as es } from "../es/agent";
import type { Strings } from "../types";

export const agent: Strings<typeof es> = {
  suggestions: {
    write: "Prépare une publication pour demain à 10 h sur tous mes canaux",
    week: "Qu’est-ce que j’ai de programmé cette semaine ?",
    lastMonth: "Comment se sont passées mes publications le mois dernier ?",
  },
  unconfigured: "L’agent n’est pas encore configuré. Un opérateur de l’installation doit ajouter la clé OpenAI dans Paramètres → Installation → Intelligence artificielle.",
  readOnly: "Vous pouvez consulter les publications et les statistiques. La création ou la suppression de publications est réservée à un administrateur.",
  greeting: "Bonjour, je suis l’agent AloStudio. Je peux préparer et programmer des publications sur vos canaux, consulter votre calendrier et vous dire comment se sont passées vos publications.",
  seeInCalendar: "Voir dans le calendrier",
  newChat: "Nouveau chat",
  chat: "Chat",
  chats: "Chats",
  statusFailed: "Impossible de vérifier l’état de l’agent.",
  chatNotFound: "Ce chat est introuvable.",
  chatLoadFailed: "Impossible de charger le chat.",
  thinking: "Réflexion…",
  composer: {
    label: "Message pour l’agent",
    unavailable: "L’agent n’est pas disponible",
    placeholder: "Écrivez un message…",
    send: "Envoyer le message",
  },
  deleteFailed: "Impossible de supprimer le chat.",
  closeList: "Fermer la liste des chats",
  chatsLoadFailed: "Impossible de charger les chats.",
  noChats: "Vous n’avez pas encore de chats.",
  toConfirm: "À confirmer",
  deleteChat: "Supprimer le chat",
  pending: {
    seeLess: "Voir moins",
    seeMore: "Voir plus",
    changeHint: "Si vous voulez changer quelque chose, écrivez-le et l’agent fera une nouvelle proposition.",
    willDelete: "Cette publication va être supprimée",
    soon: "Part dans les prochaines minutes",
    at: "Part le {when}",
  },
  deleteConfirm: "Supprimer le chat « {title} » ?",
  deleteChatNamed: "Supprimer le chat {title}",
};
