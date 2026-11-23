import type { writingAssist as es } from "../es/writingAssist";
import type { Strings } from "../types";

export const writingAssist: Strings<typeof es> = {
  button: "AI",
  working: "작성 중…",
  menu: "AI 도움",
  actions: {
    improve: "문장 다듬기",
    fix: "맞춤법 고치기",
    formal: "더 격식 있게",
    friendly: "더 친근하게",
    shorter: "더 짧게",
    translate: "번역…",
    summarize: "대화 요약",
  },
  summarizeHint: "비공개 메모로 들어갑니다",
  back: "뒤로",
  writeFirst: "다듬거나 번역하려면 먼저 내용을 입력하세요.",
  tooLong: "내용이 너무 깁니다: 최대 {max}자입니다.",
  undo: "실행 취소",
  problems: {
    disabled: "이 설치에서는 AI 도움이 꺼져 있습니다.",
    action: "AI가 할 수 없는 작업입니다.",
    text: "내용이 비어 있거나 너무 깁니다.",
    language: "목록에서 언어를 고르세요.",
    conversation: "이 대화에는 아직 요약할 메시지가 없습니다.",
    budget: "이번 달 AI 지출 한도에 도달했습니다.",
    failed: "AI가 응답하지 않았습니다. 다시 시도하세요.",
  },
};
