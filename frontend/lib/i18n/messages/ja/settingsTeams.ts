import type { settingsTeams as es } from "../es/settingsTeams";
import type { Strings } from "../types";

export const settingsTeams: Strings<typeof es> = {
  back: "チーム一覧に戻る",
  loadFailed: "チームを読み込めませんでした。",
  saveFailed: "チームを保存できませんでした。",
  autoAssign: "自動割り当てを許可",
  create: "チームを作成",
  addMemberFailed: "メンバーを追加できませんでした。",
  removeMemberFailed: "メンバーを外せませんでした。",
  members: "メンバー",
  addMember: "メンバーを追加",
  availableAgents: "追加できるエージェント",
  allMembers: "すべてのエージェントがすでにこのチームのメンバーです。",
  loadingMembers: "メンバーを読み込み中…",
  membersLoadFailed: "メンバーを読み込めませんでした。",
  noMembers: "このチームにはメンバーがいません。",
  removeFromTeam: "チームから外す",
  new: "新しいチーム",
  listLoadFailed: "チームを読み込めませんでした。",
  empty: "チームはまだありません。",
  youAreMember: "メンバーです",
  noAutoAssign: "自動割り当てなし",
  deleteConfirm: "チーム「{name}」を削除しますか？",
  removeConfirm: "{name} をチームから外しますか？",
};
