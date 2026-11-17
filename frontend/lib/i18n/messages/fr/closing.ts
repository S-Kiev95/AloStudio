import type { closing as es } from "../es/closing";
import type { Strings } from "../types";

export const closing: Strings<typeof es> = {
  settings: {
    title: "Notes de clôture",
    intro: "En résolvant une conversation depuis le panneau, l'agent indique pourquoi elle se clôt. Les statistiques comptent les clôtures par motif.",
    enabled: "Demander le motif à la résolution",
    enabledHint: "Une fenêtre propose les motifs et une note facultative. Les automatisations et les actions groupées résolvent sans demander.",
    required: "Rendre le motif obligatoire",
    requiredHint: "Sans motif, impossible de résoudre depuis le panneau.",
    categories: "Motifs",
    categoriesHint: "Jusqu'à 30, dans l'ordre d'affichage. Si vous en renommez un, les clôtures précédentes gardent l'ancien nom.",
    category: "Motif {n}",
    add: "Ajouter un motif",
    remove: "Retirer {category}",
    save: "Enregistrer",
    saved: "Enregistré.",
  },
  dialog: {
    title: "Résoudre la conversation",
    question: "Pourquoi se clôt-elle ?",
    optional: "Le motif est facultatif.",
    note: "Note (facultative)",
    notePlaceholder: "Ce qu'il faut savoir si le client réécrit",
    cancel: "Annuler",
    resolve: "Résoudre",
  },
  report: {
    title: "Motifs de clôture",
    total: "Clôtures avec motif ou note : {count}",
    none: "Note seulement",
    empty: "Aucune clôture avec motif sur cette période pour l'instant.",
    off: "Les notes de clôture sont désactivées.",
    turnOn: "Les activer dans les Réglages",
    failed: "Impossible de charger les motifs de clôture.",
  },
  problems: {
    disabled: "Les notes de clôture sont désactivées.",
    required: "Choisissez un motif pour résoudre.",
    category: "Ce motif n'est plus dans la liste. Choisissez-en un autre.",
    note: "La note peut faire jusqu'à 2 000 caractères.",
    categories: "Il faut entre 1 et 30 motifs.",
    category_length: "Chaque motif peut faire jusqu'à 60 caractères.",
    duplicate_category: "Deux motifs sont identiques.",
    failed: "Impossible d'enregistrer. Réessayez.",
  },
};
