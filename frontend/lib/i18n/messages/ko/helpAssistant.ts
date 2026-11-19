import type { helpAssistant as es } from "../es/helpAssistant";
import type { Strings } from "../types";

export const helpAssistant: Strings<typeof es> = {
  title: "도움말",
  intro: "AloStudio에서 무언가를 하는 방법을 물어보면 해당 화면으로 안내합니다.",
  examples: "예: “대화를 다른 사람에게 넘기려면?” 또는 “비밀번호는 어디서 바꾸나요?”",
  question: "질문",
  placeholder: "어떻게 하나요…?",
  ask: "질문하기",
  thinking: "도움말을 찾는 중… 몇 초 걸릴 수 있습니다.",
  goTo: "{screen}(으)로 이동",
  modeLabel: "모드",
  modeFree: "Free",
  modeFreeHint: "무료, 조금 느림",
  modeFast: "Fast",
  modeFastHint: "더 빠름, OpenAI 비용 발생",
  thinkingFast: "도움말을 찾는 중…",
  allowFast: "이 계정에서 Fast 모드 허용 (OpenAI 비용 발생)",
  problems: {
    mode: "이 계정에서는 해당 모드를 쓸 수 없습니다.",
    budget: "이번 달 AI 지출 한도에 도달했습니다. Free 모드를 사용하세요.",
    disabled: "이 설치에서는 도움말이 켜져 있지 않습니다.",
    question: "질문을 입력하세요.",
    busy: "도움말을 준비하는 중입니다. 몇 분 후 다시 시도하세요.",
    failed: "도움말이 응답하지 않았습니다. 다시 시도하세요.",
  },
};
