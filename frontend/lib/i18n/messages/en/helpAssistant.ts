import type { helpAssistant as es } from "../es/helpAssistant";
import type { Strings } from "../types";

export const helpAssistant: Strings<typeof es> = {
  title: "Help",
  intro: "Ask how to do something in AloStudio and I'll guide you to the screen.",
  examples: "For example: “how do I hand a conversation to someone else?” or “where do I change my password?”.",
  question: "Your question",
  placeholder: "How do I…?",
  ask: "Ask",
  thinking: "Looking in the help… this may take a few seconds.",
  goTo: "Go to {screen}",
  modeLabel: "Mode",
  modeFree: "Free",
  modeFreeHint: "No cost, a bit slower",
  modeFast: "Fast",
  modeFastHint: "Faster, spends on OpenAI",
  thinkingFast: "Looking in the help…",
  allowFast: "Allow Fast mode in this account (spends on OpenAI)",
  problems: {
    mode: "That mode isn't available in this account.",
    budget: "This month's AI spending cap was reached. Use Free mode.",
    disabled: "Help isn't turned on in this installation.",
    question: "Write your question.",
    busy: "Help is getting ready. Try again in a few minutes.",
    failed: "Help didn't answer. Try again.",
  },
};
