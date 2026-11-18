import type { handoff as es } from "../es/handoff";
import type { Strings } from "../types";

export const handoff: Strings<typeof es> = {
  ai: "IA da AloStudio",
  nobody: "Ninguém",
  settings: {
    title: "Transferência",
    intro: "Quando o agente da Meta ou a IA passam uma conversa para a equipe e ninguém está atribuído, ela fica com o responsável correspondente: primeiro o do chat (escolhido no painel do contato), depois o da primeira etiqueta que tiver, depois o da caixa de entrada (Configurações → Caixas de entrada) e por último o geral. Se nenhum se aplicar, toda a caixa é avisada.",
    labels: "Por etiqueta",
    labelsHint: "Vale a primeira regra, de cima para baixo, cuja etiqueta a conversa tiver.",
    noLabelRules: "Ainda não há regras por etiqueta.",
    label: "Etiqueta da regra {n}",
    target: "Responsável da regra {n}",
    pickLabel: "Escolha uma etiqueta",
    pickTarget: "Escolha um responsável",
    up: "Subir a regra {n}",
    down: "Descer a regra {n}",
    remove: "Remover a regra {n}",
    add: "Adicionar regra",
    noLabels: "Para transferir por etiqueta, crie etiquetas em Configurações → Etiquetas.",
    account: "Responsável geral",
    accountHint: "Fica com o que nenhuma regra nem a caixa resolvem.",
    save: "Salvar",
    saved: "Salvo.",
  },
  contact: {
    title: "Transferência deste chat",
    byRules: "Conforme as regras",
    hint: "Quando um bot transferir este contato, esta pessoa fica com ele antes das etiquetas e da caixa.",
  },
  problems: {
    failed: "Não foi possível salvar. Tente de novo.",
    loadFailed: "Não foi possível carregar as regras.",
    one_target: "Escolha uma pessoa ou a IA, não as duas.",
    ai_unavailable: "Esta conta ainda não tem a IA da AloStudio.",
    not_a_member: "Essa pessoa não faz mais parte da conta.",
    too_many: "Regras demais (máximo 50).",
    repeated_label: "Uma etiqueta está repetida em duas regras.",
    unknown_label: "Uma das etiquetas não existe mais.",
    no_target: "Cada regra precisa de um responsável.",
  },
};
