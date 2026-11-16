import type { hc as es } from "../es/hc";
import type { Strings } from "../types";

export const hc: Strings<typeof es> = {
  articleEmpty: "이 문서에는 아직 내용이 없습니다.",
  categoryEmpty: "이 카테고리에는 아직 게시된 문서가 없습니다.",
  errorTitle: "도움말 센터를 불러오지 못했습니다",
  errorBody: "잠시 후 새로고침해 보세요.",
  notFoundTitle: "이 문서를 찾지 못했습니다",
  notFoundBody: "더 이상 게시되지 않았거나 링크가 바뀌었을 수 있습니다.",
  categories: "카테고리",
  recentArticles: "최근 문서",
  noArticles: "아직 게시된 문서가 없습니다.",
  backToSite: "사이트로 돌아가기",
  poweredBy: "Powered by AloStudio",
};
