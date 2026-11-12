import type { actions as es } from "../es/actions";
import type { Strings } from "../types";

export const actions: Strings<typeof es> = {
  apply: "적용",
  cancel: "취소",
  selectPlaceholder: "선택…",
  edit: "편집",
  clear: "지우기",
  previous: "이전",
  next: "다음",
  addPlaceholder: "추가…",
  back: "뒤로",
  send: "보내기",
  close: "닫기",
  retry: "다시 시도",
  discard: "버리기",
  yes: "예",
  no: "아니요",
  page: "{n}페이지",
};
