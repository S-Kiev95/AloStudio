import type { googleCalendar as es } from "../es/googleCalendar";
import type { Strings } from "../types";

export const googleCalendar: Strings<typeof es> = {
  title: "Google 캘린더",
  intro: "아젠다의 예약과 날짜가 있는 CRM 작업이 Google 캘린더에 표시되고 5분마다 자동으로 업데이트됩니다. 수정은 AloStudio에서 합니다.",
  connect: "Google 캘린더 연결",
  reconnect: "다시 연결",
  disconnect: "연결 해제",
  connectedAs: "{email}(으)로 연결됨",
  lastSync: "마지막 동기화: {when}",
  waiting: "첫 동기화는 몇 분 후에 이루어집니다",
  revoked: "Google이 더 이상 캘린더 접근을 허용하지 않습니다. 다시 연결하세요.",
  syncFailed: "마지막 동기화에 실패했습니다: {detail}",
  connecting: "캘린더를 연결하는 중…",
  back: "AloStudio로 돌아가기",
  problems: {
    unavailable: "이 설치에는 Google이 설정되어 있지 않습니다.",
    state: "링크가 만료되었거나 다른 사람의 링크입니다. 다시 시도하세요.",
    exchange: "Google이 연결을 받아들이지 않았습니다. 다시 시도하세요.",
    no_refresh_token: "Google이 지속적인 접근을 허용하지 않았습니다. 다시 시도하세요.",
    cancelled: "Google 연결이 취소되었습니다.",
    failed: "Google에 연결할 수 없습니다.",
  },
};
