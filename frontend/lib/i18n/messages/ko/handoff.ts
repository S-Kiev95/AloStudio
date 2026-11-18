import type { handoff as es } from "../es/handoff";
import type { Strings } from "../types";

export const handoff: Strings<typeof es> = {
  ai: "AloStudio AI",
  nobody: "없음",
  settings: {
    title: "인계",
    intro: "Meta 에이전트나 AI가 대화를 팀에 넘기고 담당자가 없으면, 해당하는 담당자가 맡습니다. 먼저 채팅 담당자(연락처 패널에서 지정), 다음으로 대화에 붙은 첫 번째 라벨의 담당자, 다음으로 받은편지함 담당자(설정 → 받은편지함), 마지막으로 기본 담당자입니다. 아무것도 해당하지 않으면 받은편지함 전체에 알립니다.",
    labels: "라벨별",
    labelsHint: "위에서부터, 대화에 붙은 라벨의 첫 번째 규칙이 적용됩니다.",
    noLabelRules: "아직 라벨별 규칙이 없습니다.",
    label: "규칙 {n}의 라벨",
    target: "규칙 {n}의 담당자",
    pickLabel: "라벨 선택",
    pickTarget: "담당자 선택",
    up: "규칙 {n} 위로",
    down: "규칙 {n} 아래로",
    remove: "규칙 {n} 삭제",
    add: "규칙 추가",
    noLabels: "라벨별로 인계하려면 먼저 설정 → 라벨에서 라벨을 만드세요.",
    account: "기본 담당자",
    accountHint: "어떤 규칙이나 받은편지함에도 해당하지 않는 대화를 맡습니다.",
    save: "저장",
    saved: "저장했습니다.",
  },
  contact: {
    title: "이 채팅의 인계",
    byRules: "규칙에 따름",
    hint: "봇이 이 연락처를 넘기면 라벨과 받은편지함보다 먼저 이 사람이 맡습니다.",
  },
  problems: {
    failed: "저장하지 못했습니다. 다시 시도하세요.",
    loadFailed: "규칙을 불러오지 못했습니다.",
    one_target: "사람 또는 AI 중 하나만 선택하세요.",
    ai_unavailable: "이 계정에는 아직 AloStudio AI가 없습니다.",
    not_a_member: "그 사람은 더 이상 계정 구성원이 아닙니다.",
    too_many: "규칙이 너무 많습니다(최대 50개).",
    repeated_label: "같은 라벨이 두 규칙에 있습니다.",
    unknown_label: "라벨 중 하나가 더 이상 없습니다.",
    no_target: "모든 규칙에는 담당자가 필요합니다.",
  },
};
