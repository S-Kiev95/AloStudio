import type { settingsCsat as es } from "../es/settingsCsat";
import type { Strings } from "../types";

export const settingsCsat: Strings<typeof es> = {
  metricsFailed: "Impossible de charger les indicateurs CSAT.",
  rating: "Note",
  responses: "Réponses",
  responsesFailed: "Impossible de charger les réponses.",
  noResponses: "Aucune réponse sur cette période.",
  surveysSent: "Enquêtes envoyées",
  responseRate: "Taux de réponse",
  average: "Moyenne",
  distribution: "Répartition",
  anonymous: "Anonyme",
  noComment: "(sans commentaire)",
  agent: "Agent : {name}",
};
