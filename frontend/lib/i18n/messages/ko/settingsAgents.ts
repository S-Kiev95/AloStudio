import type { settingsAgents as es } from "../es/settingsAgents";
import type { Strings } from "../types";

export const settingsAgents: Strings<typeof es> = {
  nameEmailRequired: "이름과 이메일은 필수입니다.",
  inviteFailed: "초대를 보내지 못했습니다.",
  invite: "상담원 초대",
  role: "역할",
  roles: {
    agent: "상담원",
    administrator: "관리자",
  },
  inviteNote: "비밀번호를 설정할 수 있는 링크가 이메일로 전송됩니다.",
  sendInvite: "초대 보내기",
  loadFailed: "상담원을 불러오지 못했습니다.",
  empty: "이 계정에는 아직 상담원이 없습니다.",
  roleFailed: "역할을 변경하지 못했습니다.",
  removeFromAccount: "계정에서 제거",
  removeConfirm: "{name} 님을 계정에서 제거할까요?",
  removeNamed: "{name} 제거",
  invited: "{email}(으)로 초대를 보냈습니다. 비밀번호를 설정하면 링크가 만료됩니다.",
};
