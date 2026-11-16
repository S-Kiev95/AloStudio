import type { settingsTeams as es } from "../es/settingsTeams";
import type { Strings } from "../types";

export const settingsTeams: Strings<typeof es> = {
  back: "Retour aux équipes",
  loadFailed: "Impossible de charger l’équipe.",
  saveFailed: "Impossible d’enregistrer l’équipe.",
  autoAssign: "Autoriser l’attribution automatique",
  create: "Créer l’équipe",
  addMemberFailed: "Impossible d’ajouter le membre.",
  removeMemberFailed: "Impossible de retirer le membre.",
  members: "Membres",
  addMember: "Ajouter un membre",
  availableAgents: "Agents disponibles",
  allMembers: "Tous les agents sont déjà membres de cette équipe.",
  loadingMembers: "Chargement des membres…",
  membersLoadFailed: "Impossible de charger les membres.",
  noMembers: "L’équipe n’a aucun membre.",
  removeFromTeam: "Retirer de l’équipe",
  new: "Nouvelle équipe",
  listLoadFailed: "Impossible de charger les équipes.",
  empty: "Aucune équipe pour l’instant.",
  youAreMember: "Vous êtes membre",
  noAutoAssign: "Sans attribution automatique",
  deleteConfirm: "Supprimer l’équipe « {name} » ?",
  removeConfirm: "Retirer {name} de l’équipe ?",
};
