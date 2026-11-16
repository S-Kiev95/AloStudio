import type { settingsCsat as es } from "../es/settingsCsat";
import type { Strings } from "../types";

export const settingsCsat: Strings<typeof es> = {
  metricsFailed: "Couldn't load the CSAT metrics.",
  rating: "Rating",
  responses: "Responses",
  responsesFailed: "Couldn't load the responses.",
  noResponses: "No responses in this period.",
  surveysSent: "Surveys sent",
  responseRate: "Response rate",
  average: "Average",
  distribution: "Distribution",
  anonymous: "Anonymous",
  noComment: "(no comment)",
  agent: "Agent: {name}",
};
