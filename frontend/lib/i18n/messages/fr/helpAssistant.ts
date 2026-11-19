import type { helpAssistant as es } from "../es/helpAssistant";
import type { Strings } from "../types";

export const helpAssistant: Strings<typeof es> = {
  title: "Aide",
  intro: "Demandez comment faire quelque chose dans AloStudio et je vous guide jusqu’à l’écran.",
  examples: "Par exemple : « comment confier une conversation à quelqu’un d’autre ? » ou « où changer mon mot de passe ? ».",
  question: "Votre question",
  placeholder: "Comment faire pour… ?",
  ask: "Demander",
  thinking: "Recherche dans l’aide… cela peut prendre quelques secondes.",
  goTo: "Aller à {screen}",
  modeLabel: "Mode",
  modeFree: "Free",
  modeFreeHint: "Gratuit, un peu plus lent",
  modeFast: "Fast",
  modeFastHint: "Plus rapide, dépense chez OpenAI",
  thinkingFast: "Recherche dans l’aide…",
  allowFast: "Autoriser le mode Fast dans ce compte (dépense chez OpenAI)",
  problems: {
    mode: "Ce mode n’est pas disponible dans ce compte.",
    budget: "Le plafond de dépenses d’IA de ce mois est atteint. Utilisez le mode Free.",
    disabled: "L’aide n’est pas activée sur cette installation.",
    question: "Écrivez votre question.",
    busy: "L’aide se prépare. Réessayez dans quelques minutes.",
    failed: "L’aide n’a pas répondu. Réessayez.",
  },
};
