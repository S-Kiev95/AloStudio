import type { writingAssist as es } from "../es/writingAssist";
import type { Strings } from "../types";

export const writingAssist: Strings<typeof es> = {
  button: "IA",
  working: "Rédaction…",
  menu: "Aide de l’IA",
  actions: {
    improve: "Améliorer le texte",
    fix: "Corriger l’orthographe",
    formal: "Plus formel",
    friendly: "Plus chaleureux",
    shorter: "Plus court",
    translate: "Traduire en…",
    summarize: "Résumer la conversation",
  },
  summarizeHint: "Ajouté comme note privée",
  back: "Retour",
  writeFirst: "Écrivez quelque chose pour l’améliorer ou le traduire.",
  tooLong: "Le texte est trop long : {max} caractères maximum.",
  undo: "Annuler",
  problems: {
    disabled: "L’aide de l’IA est désactivée sur cette installation.",
    action: "L’IA ne sait pas faire cela.",
    text: "Le texte est vide ou trop long.",
    language: "Choisissez une langue dans la liste.",
    conversation: "La conversation n’a pas encore de messages à résumer.",
    budget: "Le plafond de dépenses d’IA de ce mois est atteint.",
    failed: "L’IA n’a pas répondu. Réessayez.",
  },
};
