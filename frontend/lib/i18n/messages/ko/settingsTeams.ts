import type { settingsTeams as es } from "../es/settingsTeams";
import type { Strings } from "../types";

export const settingsTeams: Strings<typeof es> = {
  back: "팀 목록으로 돌아가기",
  loadFailed: "팀을 불러오지 못했습니다.",
  saveFailed: "팀을 저장하지 못했습니다.",
  autoAssign: "자동 배정 허용",
  create: "팀 만들기",
  addMemberFailed: "멤버를 추가하지 못했습니다.",
  removeMemberFailed: "멤버를 제거하지 못했습니다.",
  members: "멤버",
  addMember: "멤버 추가",
  availableAgents: "추가 가능한 상담원",
  allMembers: "모든 상담원이 이미 이 팀의 멤버입니다.",
  loadingMembers: "멤버를 불러오는 중…",
  membersLoadFailed: "멤버를 불러오지 못했습니다.",
  noMembers: "이 팀에는 멤버가 없습니다.",
  removeFromTeam: "팀에서 제거",
  new: "새 팀",
  listLoadFailed: "팀을 불러오지 못했습니다.",
  empty: "아직 팀이 없습니다.",
  youAreMember: "멤버입니다",
  noAutoAssign: "자동 배정 없음",
  deleteConfirm: "\"{name}\" 팀을 삭제할까요?",
  removeConfirm: "{name} 님을 팀에서 제거할까요?",
};
