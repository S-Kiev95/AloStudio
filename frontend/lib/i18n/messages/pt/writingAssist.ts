import type { writingAssist as es } from "../es/writingAssist";
import type { Strings } from "../types";

export const writingAssist: Strings<typeof es> = {
  button: "IA",
  working: "Escrevendo…",
  menu: "Ajuda de IA",
  actions: {
    improve: "Melhorar o texto",
    fix: "Corrigir a ortografia",
    formal: "Mais formal",
    friendly: "Mais próximo",
    shorter: "Mais curto",
    translate: "Traduzir para…",
    summarize: "Resumir a conversa",
  },
  summarizeHint: "Fica como nota privada",
  back: "Voltar",
  writeFirst: "Escreva algo para melhorar ou traduzir.",
  tooLong: "O texto é muito longo: até {max} caracteres.",
  undo: "Desfazer",
  problems: {
    disabled: "A ajuda de IA está desligada nesta instalação.",
    action: "A IA não sabe fazer isso.",
    text: "O texto está vazio ou é muito longo.",
    language: "Escolha um idioma da lista.",
    conversation: "A conversa ainda não tem mensagens para resumir.",
    budget: "O limite de gasto com IA deste mês foi atingido.",
    failed: "A IA não respondeu. Tente de novo.",
  },
};
