import type { activities as es } from "../es/activities";
import type { Strings } from "../types";

export const activities: Strings<typeof es> = {
  pageTitle: "タスク",
  new: "新しいタスク",
  edit: "タスクを編集",
  create: "タスクを作成",
  kind: "種類",
  kinds: {
    task: "タスク",
    call: "電話",
    meeting: "打ち合わせ",
    email: "メール",
  },
  titlePlaceholder: "例: 申し込みの確認の電話をする",
  due: "期限",
  dueInvalid: "期限の日時が正しくありません。",
  opportunity: "商談",
  noOpportunity: "なし",
  saveFailed: "タスクを保存できませんでした。",
  deleteConfirm: "タスク「{title}」を削除しますか？",
  loadFailed: "タスクを読み込めませんでした。",
  markDone: "「{title}」を完了にする",
  groups: {
    overdue: "期限切れ",
    today: "今日",
    upcoming: "今後",
    undated: "期限なし",
    done: "完了",
  },
  show: "表示",
  pending: "未完了",
  mine: "自分のタスク",
  nonePending: "未完了のタスクはありません。",
  noneDone: "完了したタスクはまだありません。",
  noneForContact: "この連絡先に未完了のタスクはありません。",
};
