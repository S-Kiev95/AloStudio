import type { overview as es } from "../es/overview";
import type { Strings } from "../types";

export const overview: Strings<typeof es> = {
  live: {
    open: "진행 중",
    unattended: "미응답",
    unassigned: "미배정",
    pending: "대기",
  },
  shortcut: {
    conversations: "대화",
    conversationsDesc: "받은편지함",
    instagramDesc: "DM, 게시물, 댓글",
    campaigns: "캠페인",
    campaignsDesc: "발송과 템플릿",
    reports: "보고서",
    reportsDesc: "지표와 내보내기",
  },
  welcome: "환영합니다",
  intro: "모든 채널, 대화, 예약을 한곳에서. 지금 상황과 최근 7일간의 흐름입니다.",
  openInbox: "받은편지함 열기",
  goCalendar: "캘린더로 이동",
  rightNow: "지금",
  last7: "최근 7일",
  metricsFailed: "기간 지표를 불러오지 못했습니다.",
  conversations: "대화",
  shortcuts: "바로가기",
};
