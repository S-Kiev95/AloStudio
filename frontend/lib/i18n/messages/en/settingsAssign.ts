import type { settingsAssign as es } from "../es/settingsAssign";
import type { Strings } from "../types";

export const settingsAssign: Strings<typeof es> = {
  deleteConfirm: "Delete the policy \"{name}\"?",
  perWindow: "{limit} conv. / {secs}s",
  limitSentence: "At most {limit} conversations are assigned to each agent every {window} seconds.",
  priority: {
    earliest_created: "Oldest first",
    longest_waiting: "Longest waiting",
  },
  subtitle: "Automatic distribution of conversations among an inbox's agents.",
  new: "New policy",
  edit: "Edit policy",
  loadFailed: "Couldn't load the policies.",
  empty: "No policies yet.",
  limitInvalid: "The limit must be a whole number greater than 0.",
  windowInvalid: "The window must be a whole number greater than 0.",
  saveFailed: "Couldn't save the policy.",
  fairDistribution: "Fair distribution",
  optional: "Optional",
  priorityLabel: "Conversation priority",
  priorityHint: "Which waiting conversation an available agent takes first.",
  limitPerAgent: "Limit per agent",
  windowSeconds: "Window (seconds)",
  active: "Active policy",
  create: "Create policy",
};
