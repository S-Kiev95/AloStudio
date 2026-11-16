import type { settingsCsat as es } from "../es/settingsCsat";
import type { Strings } from "../types";

export const settingsCsat: Strings<typeof es> = {
  metricsFailed: "Não foi possível carregar as métricas de CSAT.",
  rating: "Avaliação",
  responses: "Respostas",
  responsesFailed: "Não foi possível carregar as respostas.",
  noResponses: "Sem respostas neste período.",
  surveysSent: "Pesquisas enviadas",
  responseRate: "Taxa de resposta",
  average: "Média",
  distribution: "Distribuição",
  anonymous: "Anônimo",
  noComment: "(sem comentário)",
  agent: "Agente: {name}",
};
