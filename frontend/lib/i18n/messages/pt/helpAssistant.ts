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
  modeLabel: "Modo",
  modeFree: "Free",
  modeFreeHint: "Sem custo, demora um pouco mais",
  modeFast: "Fast",
  modeFastHint: "Mais rápido, gasta com a OpenAI",
  thinkingFast: "Procurando na ajuda…",
  allowFast: "Permitir o modo Fast nesta conta (gasta com a OpenAI)",
  problems: {
    limit: "A IA gratuita atingiu o limite por enquanto. Tente mais tarde ou use o modo Fast.",
    mode: "Esse modo não está disponível nesta conta.",
    budget: "O limite de gasto com IA deste mês foi atingido. Use o modo Free.",
    disabled: "A ajuda não está ligada nesta instalação.",
    question: "Escreva sua pergunta.",
    busy: "A ajuda está se preparando. Tente de novo em alguns minutos.",
    failed: "A ajuda não respondeu. Tente de novo.",
  },
};
