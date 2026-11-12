import type { settingsAttrs as es } from "../es/settingsAttrs";
import type { Strings } from "../types";

export const settingsAttrs: Strings<typeof es> = {
  displayNameRequired: "표시 이름은 필수입니다.",
  saveFailed: "속성을 저장하지 못했습니다.",
  displayName: "표시 이름",
  appliesTo: "적용 대상",
  regex: "패턴 (정규식)",
  regexHint: "사용자 안내",
  regexHintPlaceholder: "예: ABC-1234",
  values: "값",
  noValues: "목록에 아직 값이 없습니다.",
  newValue: "새 값",
  create: "속성 만들기",
  new: "새 속성",
  edit: "속성 편집",
  model: "모델",
  loadFailed: "속성을 불러오지 못했습니다.",
  empty: "아직 정의된 속성이 없습니다.",
  deleteConfirm: "\"{name}\"을(를) 삭제할까요?",
  keyReadonly: "키: {key} (편집 불가)",
};
