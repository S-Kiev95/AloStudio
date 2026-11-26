import type { businessProfile as es } from "../es/businessProfile";
import type { Strings } from "../types";

export const businessProfile: Strings<typeof es> = {
  title: "비즈니스 소개",
  intro: "회사가 하는 일과 운영 방식을 한 번만 적어 주세요. 계정의 모든 AI 에이전트(통화 응대, 대화 분류, 채팅 응답)가 이 내용을 읽습니다.",
  label: "비즈니스 설명",
  placeholder: "판매하는 상품이나 제공하는 서비스, 영업시간, 주소, 결제 방법, 교환·반품 정책, 자주 묻는 질문, 하지 말아야 할 일…",
  hint: "가격과 상품은 카탈로그에서, 자세한 답변은 도움말 센터에서 읽습니다. 여기에는 그 밖의 내용을 적으세요.",
  readOnly: "계정 관리자가 수정합니다.",
  loading: "불러오는 중…",
  loadFailed: "설명을 불러오지 못했습니다.",
  save: "저장",
  saved: "저장했습니다.",
  saveFailed: "저장하지 못했습니다(최대 8,000자).",
};
