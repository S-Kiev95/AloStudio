import type { settingsPlugs as es } from "../es/settingsPlugs";
import type { Strings } from "../types";

export const settingsPlugs: Strings<typeof es> = {
  messageTooLong: "메시지가 최대 {max}자를 넘었습니다 ({count}/{max}).",
  channelPlugs: "{name} 플러그",
  whenLikes: "좋아요 {n}개에 도달하면",
  channelRequired: "플러그를 설정할 채널을 선택하세요.",
  actionRequired: "카탈로그에서 동작을 선택하세요.",
  thresholdMin: "기준값은 좋아요 1개 이상이어야 합니다.",
  messageRequired: "이 동작의 메시지를 작성하세요.",
  saveFailed: "플러그를 저장하지 못했습니다.",
  updateFailed: "플러그를 업데이트하지 못했습니다.",
  deleteFailed: "플러그를 삭제하지 못했습니다.",
  title: "플러그",
  intro: "게시물의 좋아요가 기준값에 도달하면 자동 동작을 실행합니다.",
  loadFailed: "플러그를 불러오지 못했습니다.",
  connectThreads: "자동 동작을 사용하려면 Threads를 연결하세요",
  noChannels: "카탈로그에 사용 가능한 동작이 있는 연결된 채널이 없습니다.",
  goToCalendar: "캘린더에서 채널 연결하기",
  add: "플러그 추가",
  noneInChannel: "이 채널에는 설정된 자동 동작이 없습니다.",
  edit: "플러그 편집",
  delete: "플러그 삭제",
  lastRuns: "최근 실행",
  runOk: "성공",
  runFailed: "실패",
  channel: "채널",
  thresholdLabel: "좋아요 N개에 도달하면",
  message: "메시지",
  messagePlaceholder: "자동 답장을 작성하세요…",
  save: "플러그 저장",
  kinds: {
    reply_after_likes: {
      label: "좋아요 N개에 도달하면 답글",
      description: "게시물의 좋아요가 그 수에 도달하면 그 게시물에 답글로 메시지를 게시합니다(예: 링크나 혜택).",
    },
    repost_after_likes: {
      label: "좋아요 N개에 도달하면 리포스트",
      description: "게시물의 좋아요가 그 수에 도달하면 팔로워가 다시 볼 수 있도록 프로필에 리포스트합니다.",
    },
  },
};
