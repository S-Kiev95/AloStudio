import type { settingsAgents as es } from "../es/settingsAgents";
import type { Strings } from "../types";

export const settingsAgents: Strings<typeof es> = {
  nameEmailRequired: "名前とメールアドレスは必須です。",
  inviteFailed: "招待を送信できませんでした。",
  invite: "エージェントを招待",
  role: "役割",
  roles: {
    agent: "エージェント",
    administrator: "管理者",
  },
  inviteNote: "パスワードを設定するためのリンクがメールで届きます。",
  sendInvite: "招待を送信",
  loadFailed: "エージェントを読み込めませんでした。",
  empty: "このアカウントにはまだエージェントがいません。",
  roleFailed: "役割を変更できませんでした。",
  removeFromAccount: "アカウントから外す",
  removeConfirm: "{name} をアカウントから外しますか？",
  removeNamed: "{name} を外す",
  invited: "{email} に招待を送りました。リンクはパスワードの設定後に無効になります。",
};
