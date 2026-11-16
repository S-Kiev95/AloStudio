import type { settingsSignatures as es } from "../es/settingsSignatures";
import type { Strings } from "../types";

export const settingsSignatures: Strings<typeof es> = {
  tooLong: "La signature ne peut pas dépasser {max} caractères.",
  textRequired: "Écrivez le texte de la signature.",
  saveFailed: "Impossible d’enregistrer la signature.",
  updateFailed: "Impossible de mettre à jour la signature.",
  deleteFailed: "Impossible de supprimer la signature.",
  title: "Signatures",
  intro: "Vous pouvez ajouter des signatures à votre compte pour les réutiliser dans vos publications ou en ajouter une automatiquement à chaque nouvelle publication.",
  add: "Ajouter une signature",
  loadFailed: "Impossible de charger les signatures.",
  empty: "Aucune signature pour l’instant.",
  auto: "Automatique",
  unsetAuto: "Retirer l’automatique",
  setAuto: "Rendre automatique",
  edit: "Modifier la signature",
  delete: "Supprimer la signature",
  text: "Texte de la signature",
  textPlaceholder: "Ex. : Écrivez-nous en message privé ou sur notre site.",
  autoQuestion: "L’ajouter automatiquement à chaque nouvelle publication ?",
  save: "Enregistrer la signature",
};
