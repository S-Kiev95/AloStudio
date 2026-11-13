import type { activities as es } from "../es/activities";
import type { Strings } from "../types";

export const activities: Strings<typeof es> = {
  pageTitle: "Tarefas",
  new: "Nova tarefa",
  edit: "Editar tarefa",
  create: "Criar tarefa",
  kind: "Tipo",
  kinds: {
    task: "Tarefa",
    call: "Ligação",
    meeting: "Reunião",
    email: "Email",
  },
  titlePlaceholder: "Ex.: Ligar para confirmar a inscrição",
  due: "Vence",
  dueInvalid: "A data de vencimento não é válida.",
  opportunity: "Oportunidade",
  noOpportunity: "Nenhuma",
  saveFailed: "Não foi possível salvar a tarefa.",
  deleteConfirm: "Excluir a tarefa \"{title}\"?",
  loadFailed: "Não foi possível carregar as tarefas.",
  markDone: "Marcar \"{title}\" como feita",
  groups: {
    overdue: "Vencidas",
    today: "Hoje",
    upcoming: "Próximas",
    undated: "Sem data",
    done: "Feitas",
  },
  show: "Mostrar",
  pending: "Pendentes",
  mine: "Minhas",
  nonePending: "Não há tarefas pendentes.",
  noneDone: "Ainda não há tarefas feitas.",
  noneForContact: "Este contato não tem tarefas pendentes.",
};
