import type { oauth as es } from "../es/oauth";
import type { Strings } from "../types";

export const oauth: Strings<typeof es> = {
  scope: {
    readPosts: "게시물, 채널, 통계 보기",
    readConversations: "대화와 연락처 보기",
    writePosts: "게시물 예약 및 삭제",
    writeConversations: "대화에 답장하고 정리하기",
  },
  cannotAuthorize: "승인할 수 없습니다",
  invalidRequest: "앱의 요청이 올바르지 않습니다.",
  backToApp: "AloStudio로 돌아가기",
  createdBy: "만든 곳",
  willBeAbleTo: "다음 작업을 할 수 있습니다:",
  whichAccount: "어느 계정인가요?",
  roleNotAllowed: "이 계정에서의 역할로는 이 접근을 허용할 수 없습니다",
  sendFailed: "응답을 보내지 못했습니다.",
  authorize: "승인",
  wantsAccess: "{app}이(가) AloStudio 계정에 접근하려고 합니다",
  redirectNote: "{host}(으)로 이동합니다. 접근 권한은 설정 → OAuth 앱에서 언제든 해제할 수 있습니다.",
};
