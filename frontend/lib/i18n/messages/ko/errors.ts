import type { errors as es } from "../es/errors";
import type { Strings } from "../types";

export const errors: Strings<typeof es> = {
  sectionTitle: "이 섹션을 불러오지 못했습니다",
  sectionBody: "데이터를 가져오는 중 문제가 생겼습니다. 잠시 후 다시 시도하세요.",
  accountNotFoundTitle: "찾으시는 내용을 찾지 못했습니다",
  accountNotFoundBody: "이 계정에 해당 경로가 없습니다.",
  noAccountsTitle: "계정 없음",
  noAccountsBody: "아직 이 사용자와 연결된 계정이 없습니다.",
  pageTitle: "문제가 발생했습니다",
  pageBody: "이 페이지를 불러오는 중 문제가 생겼습니다. 새로고침해 보세요.",
  goHome: "홈으로",
  notFoundTitle: "페이지를 찾을 수 없습니다",
  notFoundBody: "URL이 없거나 콘텐츠를 더 이상 사용할 수 없습니다.",
};
