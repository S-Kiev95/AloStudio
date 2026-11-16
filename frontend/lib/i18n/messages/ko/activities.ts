import type { activities as es } from "../es/activities";
import type { Strings } from "../types";

export const activities: Strings<typeof es> = {
  pageTitle: "작업",
  new: "새 작업",
  edit: "작업 편집",
  create: "작업 만들기",
  kind: "유형",
  kinds: {
    task: "작업",
    call: "전화",
    meeting: "미팅",
    email: "이메일",
  },
  titlePlaceholder: "예: 등록 확인 전화하기",
  due: "기한",
  dueInvalid: "기한 날짜가 올바르지 않습니다.",
  opportunity: "영업 기회",
  noOpportunity: "없음",
  saveFailed: "작업을 저장하지 못했습니다.",
  deleteConfirm: "\"{title}\" 작업을 삭제할까요?",
  loadFailed: "작업을 불러오지 못했습니다.",
  markDone: "\"{title}\"을(를) 완료로 표시",
  groups: {
    overdue: "기한 지남",
    today: "오늘",
    upcoming: "예정",
    undated: "날짜 없음",
    done: "완료",
  },
  show: "보기",
  pending: "진행 중",
  mine: "내 작업",
  nonePending: "진행 중인 작업이 없습니다.",
  noneDone: "아직 완료한 작업이 없습니다.",
  noneForContact: "이 연락처에는 진행 중인 작업이 없습니다.",
};
