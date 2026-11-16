import type { overview as es } from "../es/overview";
import type { Strings } from "../types";

export const overview: Strings<typeof es> = {
  live: {
    open: "Abertas",
    unattended: "Sem atendimento",
    unassigned: "Sem atribuição",
    pending: "Pendentes",
  },
  shortcut: {
    conversations: "Conversas",
    conversationsDesc: "Caixa de entrada",
    instagramDesc: "DMs, posts e comentários",
    campaigns: "Campanhas",
    campaignsDesc: "Envios e modelos",
    reports: "Relatórios",
    reportsDesc: "Métricas e exportações",
  },
  welcome: "Bem-vindo",
  intro: "Todos os seus canais, conversas e agendamentos num só lugar. Veja como estão as coisas agora e nos últimos 7 dias.",
  openInbox: "Abrir caixa de entrada",
  goCalendar: "Ir para o calendário",
  rightNow: "Agora mesmo",
  last7: "Últimos 7 dias",
  metricsFailed: "Não conseguimos carregar as métricas do período.",
  conversations: "Conversas",
  shortcuts: "Atalhos",
};
