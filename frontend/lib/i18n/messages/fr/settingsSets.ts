import type { settingsSets as es } from "../es/settingsSets";
import type { Strings } from "../types";

export const settingsSets: Strings<typeof es> = {
  title: "Sets ({count})",
  channelsLabel: "Canaux : {names}",
  deleteFailed: "Impossible de supprimer le set.",
  intro: "Gérez vos sets de contenu pour les réutiliser facilement dans vos publications.",
  add: "Ajouter un set",
  loadFailed: "Impossible de charger les sets.",
  empty: "Aucun set enregistré pour l’instant.",
  noChannels: "Aucun canal",
  edit: "Modifier le set",
  delete: "Supprimer le set",
};
