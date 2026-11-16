import type { settingsCsat as es } from "../es/settingsCsat";
import type { Strings } from "../types";

export const settingsCsat: Strings<typeof es> = {
  metricsFailed: "CSAT 지표를 불러오지 못했습니다.",
  rating: "평점",
  responses: "응답",
  responsesFailed: "응답을 불러오지 못했습니다.",
  noResponses: "이 기간에는 응답이 없습니다.",
  surveysSent: "보낸 설문",
  responseRate: "응답률",
  average: "평균",
  distribution: "분포",
  anonymous: "익명",
  noComment: "(댓글 없음)",
  agent: "상담원: {name}",
};
