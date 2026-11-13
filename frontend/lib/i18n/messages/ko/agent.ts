import type { agent as es } from "../es/agent";
import type { Strings } from "../types";

export const agent: Strings<typeof es> = {
  suggestions: {
    write: "내일 10시에 모든 채널에 올릴 게시물을 만들어 줘",
    week: "이번 주에 예약된 게 뭐야?",
    lastMonth: "지난달 게시물 성과는 어땠어?",
  },
  unconfigured: "에이전트가 아직 설정되지 않았습니다. 설치 운영자가 설정 → 설치 → 인공지능에서 OpenAI 키를 등록해야 합니다.",
  readOnly: "게시물과 통계를 조회할 수 있습니다. 게시물 생성이나 삭제는 관리자가 합니다.",
  greeting: "안녕하세요, AloStudio 에이전트입니다. 채널에 올릴 게시물을 만들고 예약하고, 캘린더를 확인하고, 게시물 성과를 알려 드릴 수 있어요.",
  seeInCalendar: "캘린더에서 보기",
  newChat: "새 채팅",
  chat: "채팅",
  chats: "채팅",
  statusFailed: "에이전트 상태를 확인하지 못했습니다.",
  chatNotFound: "이 채팅을 찾을 수 없습니다.",
  chatLoadFailed: "채팅을 불러오지 못했습니다.",
  thinking: "생각하는 중…",
  composer: {
    label: "에이전트에게 보낼 메시지",
    unavailable: "에이전트를 사용할 수 없습니다",
    placeholder: "메시지를 입력하세요…",
    send: "메시지 보내기",
  },
  deleteFailed: "채팅을 삭제하지 못했습니다.",
  closeList: "채팅 목록 닫기",
  chatsLoadFailed: "채팅을 불러오지 못했습니다.",
  noChats: "아직 채팅이 없습니다.",
  toConfirm: "확인 필요",
  deleteChat: "채팅 삭제",
  pending: {
    seeLess: "간략히",
    seeMore: "더 보기",
    changeHint: "바꾸고 싶은 점이 있으면 적어 주세요. 에이전트가 새 제안을 만듭니다.",
    willDelete: "이 게시물이 삭제됩니다",
    soon: "몇 분 안에 게시됩니다",
    at: "{when}에 게시",
  },
  deleteConfirm: "“{title}” 채팅을 삭제할까요?",
  deleteChatNamed: "{title} 채팅 삭제",
};
