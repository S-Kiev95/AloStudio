import type { actions as es } from "../es/actions";
import type { Strings } from "../types";

export const actions: Strings<typeof es> = {
  apply: "Appliquer",
  cancel: "Annuler",
  selectPlaceholder: "Sélectionner…",
  edit: "Modifier",
  clear: "Effacer",
  previous: "Précédent",
  next: "Suivant",
  addPlaceholder: "Ajouter…",
  back: "Retour",
  send: "Envoyer",
  close: "Fermer",
  retry: "Réessayer",
  discard: "Abandonner",
  yes: "Oui",
  no: "Non",
  page: "Page {n}",
  delete: "Supprimer",
  closeDialog: "Fermer la boîte de dialogue",
  deleteFailed: "Suppression impossible.",
  save: "Enregistrer",
};
