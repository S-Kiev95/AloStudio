import type { closing as es } from "../es/closing";
import type { Strings } from "../types";

export const closing: Strings<typeof es> = {
  settings: {
    title: "Notas de encerramento",
    intro: "Ao resolver uma conversa pelo painel, o agente diz por que ela foi encerrada. As estatísticas contam quantas foram encerradas por cada motivo.",
    enabled: "Pedir o motivo ao resolver",
    enabledHint: "Aparece uma janela com os motivos e uma nota opcional. As automações e as ações em massa resolvem sem perguntar.",
    required: "Tornar o motivo obrigatório",
    requiredHint: "Sem escolher um motivo não é possível resolver pelo painel.",
    categories: "Motivos",
    categoriesHint: "Até 30, na ordem em que aparecem. Se você renomear um, os encerramentos anteriores ficam com o nome antigo.",
    category: "Motivo {n}",
    add: "Adicionar motivo",
    remove: "Remover {category}",
    save: "Salvar",
    saved: "Salvo.",
  },
  dialog: {
    title: "Resolver conversa",
    question: "Por que está sendo encerrada?",
    optional: "O motivo é opcional.",
    note: "Nota (opcional)",
    notePlaceholder: "O que é bom saber se o cliente voltar a escrever",
    cancel: "Cancelar",
    resolve: "Resolver",
  },
  report: {
    title: "Motivos de encerramento",
    total: "Encerramentos com motivo ou nota: {count}",
    none: "Só com nota",
    empty: "Ainda não há encerramentos com motivo neste período.",
    off: "As notas de encerramento estão desligadas.",
    turnOn: "Ligar em Configurações",
    failed: "Não foi possível carregar os motivos de encerramento.",
  },
  problems: {
    disabled: "As notas de encerramento estão desligadas.",
    required: "Escolha um motivo para resolver.",
    category: "Esse motivo não está mais na lista. Escolha outro.",
    note: "A nota pode ter até 2.000 caracteres.",
    categories: "Deve haver entre 1 e 30 motivos.",
    category_length: "Cada motivo pode ter até 60 caracteres.",
    duplicate_category: "Há dois motivos iguais.",
    failed: "Não foi possível salvar. Tente de novo.",
  },
};
