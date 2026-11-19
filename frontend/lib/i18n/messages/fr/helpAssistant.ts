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
  problems: {
    disabled: "L’aide n’est pas activée sur cette installation.",
    question: "Écrivez votre question.",
    busy: "L’aide se prépare. Réessayez dans quelques minutes.",
    failed: "L’aide n’a pas répondu. Réessayez.",
  },
};
