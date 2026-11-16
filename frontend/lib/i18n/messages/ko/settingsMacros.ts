import type { settingsMacros as es } from "../es/settingsMacros";
import type { Strings } from "../types";

export const settingsMacros: Strings<typeof es> = {
  action: "동작",
  noParams: "매개변수 없음",
  params: "매개변수",
  removeAction: "동작 제거",
  back: "매크로 목록으로 돌아가기",
  loadFailed: "매크로를 불러오지 못했습니다.",
  needAction: "동작을 하나 이상 추가하세요.",
  saveFailed: "매크로를 저장하지 못했습니다.",
  visibility: "공개 범위",
  personal: "개인",
  globalLong: "전체 (계정 전체에 표시)",
  actions: "동작",
  needActionHint: "매크로가 할 일을 정하려면 동작을 하나 이상 추가하세요.",
  addAction: "동작 추가",
  create: "매크로 만들기",
  new: "새 매크로",
  listLoadFailed: "매크로를 불러오지 못했습니다.",
  empty: "아직 매크로가 없습니다.",
  global: "전체",
  deleteConfirm: "\"{name}\" 매크로를 삭제할까요?",
  actionsOne: "동작 {count}개",
  actionsMany: "동작 {count}개",
  by: "작성자 {name}",
};
