import type { settingsMcp as es } from "../es/settingsMcp";
import type { Strings } from "../types";

export const settingsMcp: Strings<typeof es> = {
  rotateConfirm: "トークン「{name}」を再発行しますか？現在のトークンを使っているクライアントはすぐに失敗します。",
  deleteConfirm: "トークン「{name}」を削除しますか？",
  lastUsed: "最終使用 {when}",
  new: "新しいトークン",
  intro: "これらのトークンを使うと、API と MCP サーバー経由でアカウントを自動化し、AI エージェント、n8n、CLI などの外部ツールを AloStudio に接続できます。各トークンは読み取り、書き込み、管理のいずれかの権限でこのアカウントに紐づきます。",
  edit: "トークンを編集",
  loadFailed: "トークンを読み込めませんでした。アカウントは管理者ですか？",
  empty: "トークンはまだありません。",
  rotateFailed: "再発行できませんでした。",
  neverUsed: "未使用",
  saveNow: "今すぐ保存してください",
  shownOnce: "このトークンは一度しか表示されません。紛失した場合は再発行して新しいトークンを生成する必要があります。",
  copied: "コピーしました",
  copy: "コピー",
  saveFailed: "トークンを保存できませんでした。",
  namePlaceholder: "例: support-agent",
  permissions: "権限",
  generate: "トークンを生成",
  scopes: {
    read: "読み取り",
    write: "書き込み",
    admin: "管理者",
  },
  scopeHints: {
    read: "会話、連絡先、投稿などの読み取りのみ。",
    write: "作成と変更ができます (返信、ラベル付け、公開)。",
    admin: "管理者と同じフルアクセス。",
  },
};
