import type { handoff as es } from "../es/handoff";
import type { Strings } from "../types";

export const handoff: Strings<typeof es> = {
  ai: "AloStudio's AI",
  nobody: "Nobody",
  settings: {
    title: "Handoff",
    intro: "When Meta's agent or the AI hands a conversation to the team and nobody is assigned, the matching responsible takes it: first the chat's (set in the contact panel), then the first label's it carries, then the inbox's (Settings → Inboxes) and last the default one. If none applies, the whole inbox is notified.",
    labels: "By label",
    labelsHint: "The first rule, top to bottom, whose label the conversation carries wins.",
    noLabelRules: "No label rules yet.",
    label: "Label of rule {n}",
    target: "Responsible of rule {n}",
    pickLabel: "Pick a label",
    pickTarget: "Pick a responsible",
    up: "Move rule {n} up",
    down: "Move rule {n} down",
    remove: "Remove rule {n}",
    add: "Add rule",
    noLabels: "To hand off by label, first create labels in Settings → Labels.",
    account: "Default responsible",
    accountHint: "Takes what no rule nor the inbox covers.",
    save: "Save",
    saved: "Saved.",
  },
  contact: {
    title: "Handoff for this chat",
    byRules: "By the rules",
    hint: "When a bot hands off this contact, this person takes it before labels and the inbox.",
  },
  problems: {
    failed: "Couldn't save. Try again.",
    loadFailed: "Couldn't load the rules.",
    one_target: "Pick a person or the AI, not both.",
    ai_unavailable: "This account doesn't have AloStudio's AI yet.",
    not_a_member: "That person is no longer part of the account.",
    too_many: "Too many rules (50 at most).",
    repeated_label: "A label is repeated in two rules.",
    unknown_label: "One of the labels no longer exists.",
    no_target: "Every rule needs a responsible.",
  },
};
