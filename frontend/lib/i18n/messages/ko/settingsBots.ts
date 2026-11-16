import type { settingsBots as es } from "../es/settingsBots";
import type { Strings } from "../types";

export const settingsBots: Strings<typeof es> = {
  deleteConfirm: "\"{name}\" 봇을 삭제할까요?",
  saveFailed: "봇을 저장하지 못했습니다.",
  outgoingUrl: "발신 URL",
  outgoingUrlHint: "백엔드가 메시지 이벤트를 이 URL로 보냅니다.",
  create: "봇 만들기",
  new: "새 봇",
  edit: "봇 편집",
  loadFailed: "봇을 불러오지 못했습니다.",
  empty: "아직 봇이 없습니다.",
  secret: "시크릿:",
  rotateSecret: "시크릿 재발급",
  rotateFailed: "시크릿을 재발급하지 못했습니다.",
};
