import type { handoff as es } from "../es/handoff";
import type { Strings } from "../types";

export const handoff: Strings<typeof es> = {
  ai: "IA d'AloStudio",
  nobody: "Personne",
  settings: {
    title: "Transfert",
    intro: "Quand l'agent de Meta ou l'IA transfère une conversation à l'équipe et que personne n'est assigné, le responsable correspondant la prend : d'abord celui du chat (choisi dans le panneau du contact), puis celui de la première étiquette qu'elle porte, puis celui de la boîte (Paramètres → Boîtes de réception) et enfin le responsable par défaut. Si aucun ne s'applique, toute la boîte est prévenue.",
    labels: "Par étiquette",
    labelsHint: "La première règle, de haut en bas, dont la conversation porte l'étiquette l'emporte.",
    noLabelRules: "Aucune règle par étiquette pour l'instant.",
    label: "Étiquette de la règle {n}",
    target: "Responsable de la règle {n}",
    pickLabel: "Choisissez une étiquette",
    pickTarget: "Choisissez un responsable",
    up: "Monter la règle {n}",
    down: "Descendre la règle {n}",
    remove: "Retirer la règle {n}",
    add: "Ajouter une règle",
    noLabels: "Pour transférer par étiquette, créez d'abord des étiquettes dans Paramètres → Étiquettes.",
    account: "Responsable par défaut",
    accountHint: "Prend ce qu'aucune règle ni la boîte ne couvre.",
    save: "Enregistrer",
    saved: "Enregistré.",
  },
  contact: {
    title: "Transfert de ce chat",
    byRules: "Selon les règles",
    hint: "Quand un bot transfère ce contact, cette personne le prend avant les étiquettes et la boîte.",
  },
  problems: {
    failed: "Impossible d'enregistrer. Réessayez.",
    loadFailed: "Impossible de charger les règles.",
    one_target: "Choisissez une personne ou l'IA, pas les deux.",
    ai_unavailable: "Ce compte n'a pas encore l'IA d'AloStudio.",
    not_a_member: "Cette personne ne fait plus partie du compte.",
    too_many: "Trop de règles (50 au maximum).",
    repeated_label: "Une étiquette est répétée dans deux règles.",
    unknown_label: "Une des étiquettes n'existe plus.",
    no_target: "Chaque règle a besoin d'un responsable.",
  },
};
