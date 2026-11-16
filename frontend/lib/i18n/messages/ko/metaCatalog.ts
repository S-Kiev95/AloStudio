import type { metaCatalog as es } from "../es/metaCatalog";
import type { Strings } from "../types";

export const metaCatalog: Strings<typeof es> = {
  title: "Meta 카탈로그",
  intro: "커머스 관리자 카탈로그를 연결하면 활성 상품이 그곳으로 전송되어 WhatsApp, Instagram, Facebook에 표시할 수 있습니다.",
  howTo: "ID는 커머스 관리자 → 카탈로그 → 설정에 있습니다. 토큰은 catalog_management 권한과 카탈로그 접근 권한이 있는 시스템 사용자(비즈니스 설정 → 시스템 사용자)의 것입니다.",
  catalogId: "카탈로그 ID",
  token: "액세스 토큰",
  tokenKeep: "비워 두면 현재 토큰을 유지합니다",
  connect: "카탈로그 연결",
  disconnect: "연결 해제",
  syncNow: "지금 동기화",
  disconnectConfirm: "카탈로그 연결을 해제할까요? 이미 Meta에 있는 상품은 그대로 남습니다.",
  unnamed: "이름 없는 카탈로그",
  neverSynced: "아직 동기화하지 않았습니다.",
  lastSync: "마지막 동기화: {date} · {sent}개 전송, {failed}개 문제 있음",
  stillChecking: "Meta가 아직 전송 내용을 확인 중이었습니다. 실패한 항목은 다음 동기화 때 표시됩니다.",
  autoSync: "상품을 변경하면 몇 초 후 자동으로 전송됩니다.",
  synced: "완료: {sent}개 전송, {removed}개 삭제, {skipped}개 정보 부족, {failed}개 Meta 거부.",
  state: {
    synced: "Meta에 등록됨",
    pending: "Meta에 전송 안 됨",
    missing: "Meta에 전송되지 않음, 누락: {fields}",
    refused: "Meta가 거부함",
  },
  fields: {
    description: "설명",
    price: "가격과 통화",
    url: "링크",
    image_url: "이미지",
  },
  errors: {
    token: "Meta가 토큰을 받아들이지 않았습니다. 유효하고 만료되지 않았는지 확인하세요.",
    permission: "토큰에 해당 카탈로그 권한(catalog_management)이 없습니다.",
    catalog_id: "카탈로그 ID는 숫자만 입력합니다.",
    refused: "Meta가 요청을 거부했습니다.",
    unreachable: "Meta에 연결할 수 없습니다. 잠시 후 다시 시도하세요.",
    not_connected: "먼저 카탈로그를 연결하세요.",
  },
};
