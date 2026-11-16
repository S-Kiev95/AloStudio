import type { settingsSignatures as es } from "../es/settingsSignatures";
import type { Strings } from "../types";

export const settingsSignatures: Strings<typeof es> = {
  tooLong: "서명은 {max}자를 넘을 수 없습니다.",
  textRequired: "서명 내용을 작성하세요.",
  saveFailed: "서명을 저장하지 못했습니다.",
  updateFailed: "서명을 업데이트하지 못했습니다.",
  deleteFailed: "서명을 삭제하지 못했습니다.",
  title: "서명",
  intro: "계정에 서명을 추가해 게시물에서 재사용하거나 새 게시물마다 자동으로 붙일 수 있습니다.",
  add: "서명 추가",
  loadFailed: "서명을 불러오지 못했습니다.",
  empty: "아직 서명이 없습니다.",
  auto: "자동",
  unsetAuto: "자동 해제",
  setAuto: "자동으로 설정",
  edit: "서명 편집",
  delete: "서명 삭제",
  text: "서명 내용",
  textPlaceholder: "예: DM이나 웹사이트로 문의해 주세요.",
  autoQuestion: "새 게시물마다 자동으로 붙일까요?",
  save: "서명 저장",
};
