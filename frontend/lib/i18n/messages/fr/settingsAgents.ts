import type { settingsAgents as es } from "../es/settingsAgents";
import type { Strings } from "../types";

export const settingsAgents: Strings<typeof es> = {
  nameEmailRequired: "Le nom et l’e-mail sont obligatoires.",
  inviteFailed: "Impossible d’envoyer l’invitation.",
  invite: "Inviter un agent",
  role: "Rôle",
  roles: {
    agent: "Agent",
    administrator: "Administrateur",
  },
  inviteNote: "La personne recevra un e-mail avec un lien pour définir son mot de passe.",
  sendInvite: "Envoyer l’invitation",
  loadFailed: "Impossible de charger les agents.",
  empty: "Aucun agent dans ce compte pour l’instant.",
  roleFailed: "Impossible de changer le rôle.",
  removeFromAccount: "Retirer du compte",
  removeConfirm: "Retirer {name} du compte ?",
  removeNamed: "Retirer {name}",
  invited: "Nous avons envoyé une invitation à {email}. Le lien expire une fois le mot de passe défini.",
};
