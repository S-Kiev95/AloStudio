import type { settingsWebhooks as es } from "../es/settingsWebhooks";
import type { Strings } from "../types";

export const settingsWebhooks: Strings<typeof es> = {
  urlRequired: "URL은 필수입니다.",
  eventsRequired: "구독할 이벤트를 하나 이상 선택하세요.",
  saveFailed: "웹훅을 저장하지 못했습니다.",
  url: "URL",
  inboxOptional: "받은편지함 (선택)",
  events: "구독한 이벤트",
  create: "웹훅 만들기",
  new: "새 웹훅",
  edit: "웹훅 편집",
  loadFailed: "웹훅을 불러오지 못했습니다.",
  empty: "아직 웹훅이 없습니다.",
  deleteConfirm: "이 웹훅을 삭제할까요?",
  eventsOne: "이벤트 {count}개",
  eventsMany: "이벤트 {count}개",
};
