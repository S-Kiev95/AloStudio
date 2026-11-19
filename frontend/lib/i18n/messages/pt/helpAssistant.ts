import type { helpAssistant as es } from "../es/helpAssistant";
import type { Strings } from "../types";

export const helpAssistant: Strings<typeof es> = {
  title: "Ajuda",
  intro: "Pergunte como fazer algo no AloStudio e eu te guio pela tela.",
  examples: "Por exemplo: “como passo uma conversa para outra pessoa?” ou “onde troco minha senha?”.",
  question: "Sua pergunta",
  placeholder: "Como faço para…?",
  ask: "Perguntar",
  thinking: "Procurando na ajuda… pode levar alguns segundos.",
  goTo: "Ir para {screen}",
  problems: {
    disabled: "A ajuda não está ligada nesta instalação.",
    question: "Escreva sua pergunta.",
    busy: "A ajuda está se preparando. Tente de novo em alguns minutos.",
    failed: "A ajuda não respondeu. Tente de novo.",
  },
};
