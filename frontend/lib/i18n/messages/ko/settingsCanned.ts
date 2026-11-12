import type { settingsCanned as es } from "../es/settingsCanned";
import type { Strings } from "../types";

export const settingsCanned: Strings<typeof es> = {
  shortCodeRequired: "단축어는 필수입니다.",
  contentRequired: "내용은 필수입니다.",
  saveFailed: "답변을 저장하지 못했습니다.",
  shortCode: "단축어",
  content: "내용",
  create: "답변 만들기",
  new: "새 답변",
  search: "답변 검색",
  searchPlaceholder: "단축어 또는 내용으로 검색…",
  edit: "답변 편집",
  loadFailed: "답변을 불러오지 못했습니다.",
  noneFound: "답변을 찾지 못했습니다.",
  empty: "아직 답변이 없습니다.",
  deleteConfirm: "\"/{code}\"을(를) 삭제할까요?",
  shortCodeHint: "편집기에 {code}을(를) 입력하면 답변이 삽입됩니다.",
  shortCodeExample: "단축어",
};
