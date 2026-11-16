import type { activities as es } from "../es/activities";
import type { Strings } from "../types";

export const activities: Strings<typeof es> = {
  pageTitle: "Tâches",
  new: "Nouvelle tâche",
  edit: "Modifier la tâche",
  create: "Créer la tâche",
  kind: "Type",
  kinds: {
    task: "Tâche",
    call: "Appel",
    meeting: "Réunion",
    email: "E-mail",
  },
  titlePlaceholder: "Ex. : Appeler pour confirmer l’inscription",
  due: "Échéance",
  dueInvalid: "La date d’échéance n’est pas valide.",
  opportunity: "Opportunité",
  noOpportunity: "Aucune",
  saveFailed: "Impossible d’enregistrer la tâche.",
  deleteConfirm: "Supprimer la tâche « {title} » ?",
  loadFailed: "Impossible de charger les tâches.",
  markDone: "Marquer « {title} » comme faite",
  groups: {
    overdue: "En retard",
    today: "Aujourd’hui",
    upcoming: "À venir",
    undated: "Sans date",
    done: "Faites",
  },
  show: "Afficher",
  pending: "En attente",
  mine: "Les miennes",
  nonePending: "Aucune tâche en attente.",
  noneDone: "Aucune tâche faite pour l’instant.",
  noneForContact: "Ce contact n’a aucune tâche en attente.",
};
