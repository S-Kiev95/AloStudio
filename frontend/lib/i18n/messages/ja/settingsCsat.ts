import type { settingsCsat as es } from "../es/settingsCsat";
import type { Strings } from "../types";

export const settingsCsat: Strings<typeof es> = {
  metricsFailed: "CSAT の指標を読み込めませんでした。",
  rating: "評価",
  responses: "回答",
  responsesFailed: "回答を読み込めませんでした。",
  noResponses: "この期間の回答はありません。",
  surveysSent: "送信したアンケート",
  responseRate: "回答率",
  average: "平均",
  distribution: "分布",
  anonymous: "匿名",
  noComment: "(コメントなし)",
  agent: "エージェント: {name}",
};
