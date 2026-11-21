import type { helpAssistant as es } from "../es/helpAssistant";
import type { Strings } from "../types";

export const helpAssistant: Strings<typeof es> = {
  title: "ヘルプ",
  intro: "AloStudio での操作方法を質問すると、該当する画面まで案内します。",
  examples: "例: 「会話を別の人に渡すには?」「パスワードはどこで変更する?」",
  question: "質問",
  placeholder: "〜するには?",
  ask: "質問する",
  thinking: "ヘルプを検索しています… 数秒かかることがあります。",
  goTo: "{screen} へ移動",
  modeLabel: "モード",
  modeFree: "Free",
  modeFreeHint: "無料、少し時間がかかります",
  modeFast: "Fast",
  modeFastHint: "高速、OpenAI の費用がかかります",
  thinkingFast: "ヘルプを検索しています…",
  allowFast: "このアカウントで Fast モードを許可 (OpenAI の費用がかかります)",
  problems: {
    limit: "無料の AI は現在上限に達しています。しばらくしてから試すか、Fast モードを使ってください。",
    mode: "このアカウントではそのモードは使えません。",
    budget: "今月の AI 利用上限に達しました。Free モードを使ってください。",
    disabled: "このインストールではヘルプがオンになっていません。",
    question: "質問を入力してください。",
    busy: "ヘルプを準備中です。数分後にもう一度お試しください。",
    failed: "ヘルプから応答がありませんでした。もう一度お試しください。",
  },
};
