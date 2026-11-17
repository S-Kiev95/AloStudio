import type { closing as es } from "../es/closing";
import type { Strings } from "../types";

export const closing: Strings<typeof es> = {
  settings: {
    title: "クローズメモ",
    intro: "パネルから会話を解決するとき、担当者がクローズの理由を選びます。統計では理由ごとの件数がわかります。",
    enabled: "解決時に理由を聞く",
    enabledHint: "理由と任意のメモを入力する画面が表示されます。自動化や一括操作では聞かずに解決します。",
    required: "理由を必須にする",
    requiredHint: "理由を選ばないとパネルから解決できません。",
    categories: "理由",
    categoriesHint: "最大30件、表示される順番です。名前を変えても、以前のクローズは古い名前のままです。",
    category: "理由 {n}",
    add: "理由を追加",
    remove: "{category}を削除",
    save: "保存",
    saved: "保存しました。",
  },
  dialog: {
    title: "会話を解決",
    question: "クローズの理由は?",
    optional: "理由は任意です。",
    note: "メモ(任意)",
    notePlaceholder: "お客様がまた連絡してきたときに知っておきたいこと",
    cancel: "キャンセル",
    resolve: "解決",
  },
  report: {
    title: "クローズの理由",
    total: "理由またはメモ付きのクローズ: {count}件",
    none: "メモのみ",
    empty: "この期間に理由付きのクローズはまだありません。",
    off: "クローズメモはオフです。",
    turnOn: "設定でオンにする",
    failed: "クローズの理由を読み込めませんでした。",
  },
  problems: {
    disabled: "クローズメモはオフです。",
    required: "解決するには理由を選んでください。",
    category: "その理由はもう一覧にありません。別の理由を選んでください。",
    note: "メモは2,000文字までです。",
    categories: "理由は1〜30件にしてください。",
    category_length: "理由はそれぞれ60文字までです。",
    duplicate_category: "同じ理由が2つあります。",
    failed: "保存できませんでした。もう一度お試しください。",
  },
};
