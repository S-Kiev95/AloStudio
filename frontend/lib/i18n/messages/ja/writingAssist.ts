import type { writingAssist as es } from "../es/writingAssist";
import type { Strings } from "../types";

export const writingAssist: Strings<typeof es> = {
  button: "AI",
  working: "作成中…",
  menu: "AI アシスト",
  actions: {
    improve: "文章を改善",
    fix: "誤字を修正",
    formal: "よりフォーマルに",
    friendly: "より親しみやすく",
    shorter: "短く",
    translate: "翻訳…",
    summarize: "会話を要約",
  },
  summarizeHint: "非公開メモとして入ります",
  back: "戻る",
  writeFirst: "改善や翻訳をするには、まず文章を入力してください。",
  tooLong: "文章が長すぎます: 最大 {max} 文字です。",
  undo: "元に戻す",
  problems: {
    disabled: "このインストールでは AI アシストがオフです。",
    action: "AI はその操作に対応していません。",
    text: "文章が空か、長すぎます。",
    language: "リストから言語を選んでください。",
    conversation: "この会話にはまだ要約できるメッセージがありません。",
    budget: "今月の AI 利用上限に達しました。",
    failed: "AI から応答がありませんでした。もう一度お試しください。",
  },
};
