import type { settingsAssign as es } from "../es/settingsAssign";
import type { Strings } from "../types";

export const settingsAssign: Strings<typeof es> = {
  deleteConfirm: "Excluir a política \"{name}\"?",
  perWindow: "{limit} conv. / {secs}s",
  limitSentence: "São atribuídas no máximo {limit} conversas a cada agente a cada {window} segundos.",
  priority: {
    earliest_created: "A mais antiga primeiro",
    longest_waiting: "A que mais espera",
  },
  subtitle: "Distribuição automática de conversas entre os agentes de uma caixa de entrada.",
  new: "Nova política",
  edit: "Editar política",
  loadFailed: "Não foi possível carregar as políticas.",
  empty: "Ainda não há políticas.",
  limitInvalid: "O limite deve ser um número inteiro maior que 0.",
  windowInvalid: "A janela deve ser um número inteiro maior que 0.",
  saveFailed: "Não foi possível salvar a política.",
  fairDistribution: "Distribuição equilibrada",
  optional: "Opcional",
  priorityLabel: "Prioridade da conversa",
  priorityHint: "Qual conversa em espera um agente disponível pega primeiro.",
  limitPerAgent: "Limite por agente",
  windowSeconds: "Janela (segundos)",
  active: "Política ativa",
  create: "Criar política",
};
