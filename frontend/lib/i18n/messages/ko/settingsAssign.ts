import type { settingsAssign as es } from "../es/settingsAssign";
import type { Strings } from "../types";

export const settingsAssign: Strings<typeof es> = {
  deleteConfirm: "\"{name}\" 정책을 삭제할까요?",
  perWindow: "{limit}건 / {secs}초",
  limitSentence: "각 상담원에게 {window}초마다 최대 {limit}건의 대화가 배정됩니다.",
  priority: {
    earliest_created: "먼저 생성된 대화",
    longest_waiting: "가장 오래 기다린 대화",
  },
  subtitle: "받은편지함 상담원 간에 대화를 자동으로 분배합니다.",
  new: "새 정책",
  edit: "정책 편집",
  loadFailed: "정책을 불러오지 못했습니다.",
  empty: "아직 정책이 없습니다.",
  limitInvalid: "한도는 0보다 큰 정수여야 합니다.",
  windowInvalid: "기간은 0보다 큰 정수여야 합니다.",
  saveFailed: "정책을 저장하지 못했습니다.",
  fairDistribution: "균등 분배",
  optional: "선택 사항",
  priorityLabel: "대화 우선순위",
  priorityHint: "대기 중인 대화 중 상담원이 먼저 맡을 대화입니다.",
  limitPerAgent: "상담원별 한도",
  windowSeconds: "기간 (초)",
  active: "정책 활성화",
  create: "정책 만들기",
};
