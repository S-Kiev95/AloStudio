import type { settingsMacros as es } from "../es/settingsMacros";
import type { Strings } from "../types";

export const settingsMacros: Strings<typeof es> = {
  action: "Action",
  noParams: "Aucun paramètre",
  params: "Paramètres",
  removeAction: "Retirer l’action",
  back: "Retour aux macros",
  loadFailed: "Impossible de charger la macro.",
  needAction: "Ajoutez au moins une action.",
  saveFailed: "Impossible d’enregistrer la macro.",
  visibility: "Visibilité",
  personal: "Personnelle",
  globalLong: "Globale (visible par tout le compte)",
  actions: "Actions",
  needActionHint: "Ajoutez au moins une action pour définir ce que fait la macro.",
  addAction: "Ajouter une action",
  create: "Créer la macro",
  new: "Nouvelle macro",
  listLoadFailed: "Impossible de charger les macros.",
  empty: "Aucune macro pour l’instant.",
  global: "Globale",
  deleteConfirm: "Supprimer la macro « {name} » ?",
  actionsOne: "{count} action",
  actionsMany: "{count} actions",
  by: "par {name}",
};
