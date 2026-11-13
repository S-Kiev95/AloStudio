import type { settingsAssign as es } from "../es/settingsAssign";
import type { Strings } from "../types";

export const settingsAssign: Strings<typeof es> = {
  deleteConfirm: "ポリシー「{name}」を削除しますか？",
  perWindow: "{limit} 件 / {secs} 秒",
  limitSentence: "各エージェントには {window} 秒ごとに最大 {limit} 件の会話が割り当てられます。",
  priority: {
    earliest_created: "作成が古い順",
    longest_waiting: "待ち時間が長い順",
  },
  subtitle: "受信箱のエージェント間で会話を自動的に振り分けます。",
  new: "新しいポリシー",
  edit: "ポリシーを編集",
  loadFailed: "ポリシーを読み込めませんでした。",
  empty: "ポリシーはまだありません。",
  limitInvalid: "上限は 0 より大きい整数にしてください。",
  windowInvalid: "期間は 0 より大きい整数にしてください。",
  saveFailed: "ポリシーを保存できませんでした。",
  fairDistribution: "均等配分",
  optional: "任意",
  priorityLabel: "会話の優先順位",
  priorityHint: "空いているエージェントが最初に受け持つ待機中の会話。",
  limitPerAgent: "エージェントごとの上限",
  windowSeconds: "期間 (秒)",
  active: "ポリシーを有効にする",
  create: "ポリシーを作成",
};
