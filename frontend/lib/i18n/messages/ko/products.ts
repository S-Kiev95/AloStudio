import type { products as es } from "../es/products";
import type { Strings } from "../types";

export const products: Strings<typeof es> = {
  form: {
    nameRequired: "이름을 입력하세요.",
    priceInvalid: "가격이 올바르지 않습니다.",
    saveFailed: "상품을 저장하지 못했습니다.",
    description: "설명",
    price: "가격",
    currency: "통화",
    productUrl: "상품 URL",
    imageUrl: "이미지 URL",
    active: "활성 (카탈로그에 표시)",
    create: "상품 만들기",
  },
  filters: {
    all: "전체",
    active: "활성",
    inactive: "비활성",
  },
  title: "상품",
  new: "새 상품",
  edit: "상품 편집",
  filterLabel: "상품 필터",
  loadFailed: "상품을 불러오지 못했습니다.",
  empty: "아직 상품이 없습니다.",
  active: "활성",
  inactive: "비활성",
  deleteConfirm: "“{name}”을(를) 삭제할까요?",
  description: "설명",
};
