import type { closing as es } from "../es/closing";
import type { Strings } from "../types";

export const closing: Strings<typeof es> = {
  settings: {
    title: "종료 메모",
    intro: "패널에서 대화를 해결할 때 담당자가 종료 사유를 고릅니다. 통계에서 사유별 건수를 볼 수 있어요.",
    enabled: "해결할 때 사유 묻기",
    enabledHint: "사유와 선택 메모를 입력하는 창이 나타나요. 자동화와 일괄 작업은 묻지 않고 해결해요.",
    required: "사유를 필수로 하기",
    requiredHint: "사유를 고르지 않으면 패널에서 해결할 수 없어요.",
    categories: "사유",
    categoriesHint: "최대 30개, 표시되는 순서대로예요. 이름을 바꿔도 이전 종료 건은 예전 이름으로 남아요.",
    category: "사유 {n}",
    add: "사유 추가",
    remove: "{category} 삭제",
    save: "저장",
    saved: "저장했어요.",
  },
  dialog: {
    title: "대화 해결",
    question: "종료 사유가 무엇인가요?",
    optional: "사유는 선택 사항이에요.",
    note: "메모(선택)",
    notePlaceholder: "고객이 다시 연락하면 알아두면 좋은 내용",
    cancel: "취소",
    resolve: "해결",
  },
  report: {
    title: "종료 사유",
    total: "사유 또는 메모가 있는 종료: {count}건",
    none: "메모만",
    empty: "이 기간에 사유가 있는 종료가 아직 없어요.",
    off: "종료 메모가 꺼져 있어요.",
    turnOn: "설정에서 켜기",
    failed: "종료 사유를 불러오지 못했어요.",
  },
  problems: {
    disabled: "종료 메모가 꺼져 있어요.",
    required: "해결하려면 사유를 고르세요.",
    category: "그 사유는 더 이상 목록에 없어요. 다른 사유를 고르세요.",
    note: "메모는 최대 2,000자까지 쓸 수 있어요.",
    categories: "사유는 1~30개여야 해요.",
    category_length: "사유는 각각 최대 60자까지예요.",
    duplicate_category: "같은 사유가 두 개 있어요.",
    failed: "저장하지 못했어요. 다시 시도하세요.",
  },
};
