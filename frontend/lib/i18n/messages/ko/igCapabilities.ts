import type { igCapabilities as es } from "../es/igCapabilities";
import type { Strings } from "../types";

export const igCapabilities: Strings<typeof es> = {
  publish: "사진, 캐러셀, 릴스, 스토리 게시",
  comments: "댓글 읽기 및 답글, 자동 규칙 포함",
  insights: "게시물 지표",
  facebook: {
    summary: "모든 기능을 쓸 수 있는 방법입니다. 메시지를 응대한다면 이쪽이 좋습니다.",
    requirement: "Instagram 계정에 연결된 Facebook 페이지가 필요합니다.",
    dmsNote: "메시지가 본문과 첨부 파일과 함께 도착합니다.",
  },
  dms: "다이렉트 메시지 받기 및 답장",
  deletePosts: "AloStudio에서 게시물 삭제",
  instagram: {
    summary: "연결은 더 간단하지만 메시지는 사용할 수 없습니다.",
    requirement: "Facebook 페이지가 필요 없습니다.",
    dmsNote: "Meta는 메시지가 왔다는 알림만 보내고 본문은 보내지 않아 대화를 복원할 수 없습니다. AloStudio가 아니라 Meta의 제한입니다.",
    deleteNote: "Meta는 이 API에서 삭제를 제공하지 않습니다. Instagram 앱에서 삭제해야 합니다.",
  },
};
