import type { settingsHours as es } from "../es/settingsHours";
import type { Strings } from "../types";

export const settingsHours: Strings<typeof es> = {
  saveFailed: "운영 시간을 저장하지 못했습니다.",
  loading: "운영 시간을 불러오는 중…",
  loadFailed: "운영 시간을 불러오지 못했습니다.",
  weekly: "주간 운영 시간",
  closed: "휴무",
  allDay: "24시간",
  opens: "시작",
  closes: "종료",
  inboxesLoadFailed: "받은편지함을 불러오지 못했습니다.",
  noInboxes: "아직 연결된 받은편지함이 없습니다.",
};
