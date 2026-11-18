import type { handoff as es } from "../es/handoff";
import type { Strings } from "../types";

export const handoff: Strings<typeof es> = {
  ai: "AloStudioのAI",
  nobody: "なし",
  settings: {
    title: "引き継ぎ",
    intro: "Metaのエージェントや AI が会話をチームに引き継ぎ、担当者がいない場合、該当する担当者が引き受けます。まずチャットの担当者（連絡先パネルで設定）、次に会話に付いている最初のラベルの担当者、次に受信箱の担当者（設定 → 受信箱）、最後に全体の担当者です。どれも当てはまらない場合は受信箱全体に通知します。",
    labels: "ラベル別",
    labelsHint: "上から順に、会話に付いているラベルの最初のルールが適用されます。",
    noLabelRules: "ラベル別のルールはまだありません。",
    label: "ルール{n}のラベル",
    target: "ルール{n}の担当者",
    pickLabel: "ラベルを選択",
    pickTarget: "担当者を選択",
    up: "ルール{n}を上へ",
    down: "ルール{n}を下へ",
    remove: "ルール{n}を削除",
    add: "ルールを追加",
    noLabels: "ラベル別に引き継ぐには、まず 設定 → ラベル でラベルを作成してください。",
    account: "全体の担当者",
    accountHint: "どのルールにも受信箱にも当てはまらないものを引き受けます。",
    save: "保存",
    saved: "保存しました。",
  },
  contact: {
    title: "このチャットの引き継ぎ",
    byRules: "ルールに従う",
    hint: "ボットがこの連絡先を引き継ぐとき、ラベルや受信箱より先にこの人が引き受けます。",
  },
  problems: {
    failed: "保存できませんでした。もう一度お試しください。",
    loadFailed: "ルールを読み込めませんでした。",
    one_target: "人か AI のどちらかを選んでください。",
    ai_unavailable: "このアカウントにはまだ AloStudio の AI がありません。",
    not_a_member: "その人はもうアカウントのメンバーではありません。",
    too_many: "ルールが多すぎます（最大50）。",
    repeated_label: "同じラベルが2つのルールにあります。",
    unknown_label: "ラベルの1つが存在しません。",
    no_target: "各ルールに担当者が必要です。",
  },
};
