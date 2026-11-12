import type { settingsAttrs as es } from "../es/settingsAttrs";
import type { Strings } from "../types";

export const settingsAttrs: Strings<typeof es> = {
  displayNameRequired: "Le nom affiché est obligatoire.",
  saveFailed: "Impossible d’enregistrer l’attribut.",
  displayName: "Nom affiché",
  appliesTo: "S’applique à",
  regex: "Motif (regex)",
  regexHint: "Indication pour l’utilisateur",
  regexHintPlaceholder: "Ex. ABC-1234",
  values: "Valeurs",
  noValues: "Aucune valeur dans la liste pour l’instant.",
  newValue: "Nouvelle valeur",
  create: "Créer l’attribut",
  new: "Nouvel attribut",
  edit: "Modifier l’attribut",
  model: "Modèle",
  loadFailed: "Impossible de charger les attributs.",
  empty: "Aucun attribut défini pour l’instant.",
  deleteConfirm: "Supprimer « {name} » ?",
  keyReadonly: "Clé : {key} (non modifiable)",
};
