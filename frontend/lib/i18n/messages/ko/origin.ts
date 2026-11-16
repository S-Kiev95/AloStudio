import type { origin as es } from "../es/origin";
import type { Strings } from "../types";

export const origin: Strings<typeof es> = {
  title: "유입 경로",
  set: "유입 경로 지정",
  source: "유입 방식",
  channel: "채널",
  detail: "세부 정보",
  detailPlaceholder: "예: Juan 님 추천, 10월 박람회…",
  unknown: "지정 안 됨",
  noChannel: "없음",
  none: "아직 유입 경로를 알 수 없습니다.",
  since: "{date}부터",
  saveFailed: "유입 경로를 저장하지 못했습니다.",
  sources: {
    channel: "채널로 문의",
    ad: "광고",
    post: "게시물",
    shortlink: "직접 링크",
    referral: "추천",
    event: "이벤트·박람회",
    walk_in: "방문",
    phone: "전화",
    website: "웹사이트",
    other: "기타",
  },
  channels: {
    whatsapp: "WhatsApp",
    instagram: "Instagram",
    facebook: "Facebook",
    web: "웹사이트 채팅",
    email: "이메일",
    telegram: "Telegram",
    sms: "SMS",
    api: "API",
  },
};
