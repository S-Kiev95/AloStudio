import type { settingsCanned as es } from "../es/settingsCanned";
import type { Strings } from "../types";

export const settingsCanned: Strings<typeof es> = {
  shortCodeRequired: "Le raccourci est obligatoire.",
  contentRequired: "Le contenu est obligatoire.",
  saveFailed: "Impossible d’enregistrer la réponse.",
  shortCode: "Raccourci",
  content: "Contenu",
  create: "Créer la réponse",
  new: "Nouvelle réponse",
  search: "Rechercher des réponses",
  searchPlaceholder: "Rechercher par raccourci ou contenu…",
  edit: "Modifier la réponse",
  loadFailed: "Impossible de charger les réponses.",
  noneFound: "Aucune réponse trouvée.",
  empty: "Aucune réponse pour l’instant.",
  deleteConfirm: "Supprimer « /{code} » ?",
  shortCodeHint: "Tapez {code} dans l’éditeur pour insérer la réponse.",
  shortCodeExample: "raccourci",
};
