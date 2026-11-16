import type { settingsAssign as es } from "../es/settingsAssign";
import type { Strings } from "../types";

export const settingsAssign: Strings<typeof es> = {
  deleteConfirm: "Supprimer la politique « {name} » ?",
  perWindow: "{limit} conv. / {secs}s",
  limitSentence: "Au maximum {limit} conversations sont attribuées à chaque agent toutes les {window} secondes.",
  priority: {
    earliest_created: "La plus ancienne d’abord",
    longest_waiting: "Celle qui attend le plus",
  },
  subtitle: "Répartition automatique des conversations entre les agents d’une boîte de réception.",
  new: "Nouvelle politique",
  edit: "Modifier la politique",
  loadFailed: "Impossible de charger les politiques.",
  empty: "Aucune politique pour l’instant.",
  limitInvalid: "La limite doit être un entier supérieur à 0.",
  windowInvalid: "La fenêtre doit être un entier supérieur à 0.",
  saveFailed: "Impossible d’enregistrer la politique.",
  fairDistribution: "Répartition équilibrée",
  optional: "Facultatif",
  priorityLabel: "Priorité des conversations",
  priorityHint: "Quelle conversation en attente un agent disponible prend en premier.",
  limitPerAgent: "Limite par agent",
  windowSeconds: "Fenêtre (secondes)",
  active: "Politique active",
  create: "Créer la politique",
};
