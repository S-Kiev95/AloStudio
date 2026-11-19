import type { closing as es } from "../es/closing";
import type { Strings } from "../types";

export const closing: Strings<typeof es> = {
  settings: {
    title: "Closing notes",
    intro: "When resolving a conversation from the panel, the agent says why it closes. The reports count how many closed for each reason.",
    enabled: "Ask for the reason when resolving",
    enabledHint: "A window shows the reasons and an optional note. Automations and bulk actions resolve without asking.",
    required: "Make the reason required",
    requiredHint: "Without a reason, the panel can't resolve.",
    categories: "Reasons",
    categoriesHint: "Up to 30, in the order they show. If you rename one, earlier closings keep the old name.",
    category: "Reason {n}",
    add: "Add reason",
    remove: "Remove {category}",
    save: "Save",
    saved: "Saved.",
  },
  dialog: {
    title: "Resolve conversation",
    question: "Why is it closing?",
    optional: "The reason is optional.",
    note: "Note (optional)",
    notePlaceholder: "What to know if the customer writes again",
    cancel: "Cancel",
    resolve: "Resolve",
  },
  report: {
    title: "Closing reasons",
    total: "Closings with a reason or note: {count}",
    none: "Note only",
    empty: "No closings with a reason in this period yet.",
    off: "Closing notes are off.",
    turnOn: "Turn them on in Settings",
    failed: "Couldn't load the closing reasons.",
  },
  problems: {
    disabled: "Closing notes are off.",
    required: "Pick a reason to resolve.",
    category: "That reason is no longer on the list. Pick another.",
    note: "The note can be up to 2,000 characters.",
    categories: "There must be between 1 and 30 reasons.",
    category_length: "Each reason can be up to 60 characters.",
    duplicate_category: "Two reasons are the same.",
    failed: "Couldn't save. Try again.",
  },
};
