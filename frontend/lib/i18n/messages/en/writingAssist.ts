import type { writingAssist as es } from "../es/writingAssist";
import type { Strings } from "../types";

export const writingAssist: Strings<typeof es> = {
  button: "AI",
  working: "Writing…",
  menu: "AI help",
  actions: {
    improve: "Improve the writing",
    fix: "Fix the spelling",
    formal: "More formal",
    friendly: "Friendlier",
    shorter: "Shorter",
    translate: "Translate to…",
    summarize: "Summarize the conversation",
  },
  summarizeHint: "Goes in as a private note",
  back: "Back",
  writeFirst: "Write something to improve or translate it.",
  tooLong: "The text is too long: up to {max} characters.",
  undo: "Undo",
  problems: {
    disabled: "AI help is turned off on this installation.",
    action: "The AI can't do that.",
    text: "The text is empty or too long.",
    language: "Pick a language from the list.",
    conversation: "The conversation has no messages to summarize yet.",
    budget: "This month's AI spending cap was reached.",
    failed: "The AI didn't answer. Try again.",
  },
};
