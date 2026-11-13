import type { settingsMcp as es } from "../es/settingsMcp";
import type { Strings } from "../types";

export const settingsMcp: Strings<typeof es> = {
  rotateConfirm: "\"{name}\" 토큰을 재발급할까요? 현재 토큰을 쓰는 클라이언트는 즉시 실패합니다.",
  deleteConfirm: "\"{name}\" 토큰을 삭제할까요?",
  lastUsed: "마지막 사용 {when}",
  new: "새 토큰",
  intro: "이 토큰으로 계정을 자동화하고 AI 에이전트, n8n, CLI 같은 외부 도구를 API와 MCP 서버를 통해 AloStudio에 연결하세요. 각 토큰은 읽기, 쓰기 또는 관리 권한으로 이 계정에 연결됩니다.",
  edit: "토큰 편집",
  loadFailed: "토큰을 불러오지 못했습니다. 관리자 계정인가요?",
  empty: "아직 토큰이 없습니다.",
  rotateFailed: "재발급하지 못했습니다.",
  neverUsed: "사용한 적 없음",
  saveNow: "지금 저장하세요",
  shownOnce: "이 토큰은 한 번만 표시됩니다. 잃어버리면 재발급해서 새 토큰을 만들어야 합니다.",
  copied: "복사됨",
  copy: "복사",
  saveFailed: "토큰을 저장하지 못했습니다.",
  namePlaceholder: "예: support-agent",
  permissions: "권한",
  generate: "토큰 생성",
  scopes: {
    read: "읽기",
    write: "쓰기",
    admin: "관리자",
  },
  scopeHints: {
    read: "대화, 연락처, 게시물 등을 읽기만 할 수 있습니다.",
    write: "만들고 수정할 수 있습니다 (답장, 라벨 지정, 게시).",
    admin: "관리자와 같은 전체 접근 권한.",
  },
};
