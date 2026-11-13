import type { settingsBots as es } from "../es/settingsBots";
import type { Strings } from "../types";

export const settingsBots: Strings<typeof es> = {
  deleteConfirm: "Supprimer le bot « {name} » ?",
  saveFailed: "Impossible d’enregistrer le bot.",
  outgoingUrl: "URL de sortie",
  outgoingUrlHint: "Le backend enverra les événements de message à cette URL.",
  create: "Créer le bot",
  new: "Nouveau bot",
  edit: "Modifier le bot",
  loadFailed: "Impossible de charger les bots.",
  empty: "Aucun bot pour l’instant.",
  secret: "Secret :",
  rotateSecret: "Renouveler le secret",
  rotateFailed: "Impossible de renouveler le secret.",
};
