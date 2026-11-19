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
  problems: {
    disabled: "Help isn't turned on in this installation.",
    question: "Write your question.",
    busy: "Help is getting ready. Try again in a few minutes.",
    failed: "Help didn't answer. Try again.",
  },
};
