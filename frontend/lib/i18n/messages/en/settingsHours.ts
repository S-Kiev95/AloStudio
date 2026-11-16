import type { settingsHours as es } from "../es/settingsHours";
import type { Strings } from "../types";

export const settingsHours: Strings<typeof es> = {
  saveFailed: "Couldn't save the schedule.",
  loading: "Loading schedule…",
  loadFailed: "Couldn't load the schedule.",
  weekly: "Weekly schedule",
  closed: "Closed",
  allDay: "24 hours",
  opens: "Opens",
  closes: "Closes",
  inboxesLoadFailed: "Couldn't load the inboxes.",
  noInboxes: "No inboxes connected yet.",
};
