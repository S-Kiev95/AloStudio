import type { activities as es } from "../es/activities";
import type { Strings } from "../types";

export const activities: Strings<typeof es> = {
  pageTitle: "Tasks",
  new: "New task",
  edit: "Edit task",
  create: "Create task",
  kind: "Type",
  kinds: {
    task: "Task",
    call: "Call",
    meeting: "Meeting",
    email: "Email",
  },
  titlePlaceholder: "E.g. Call to confirm the enrollment",
  due: "Due",
  dueInvalid: "The due date isn't valid.",
  opportunity: "Opportunity",
  noOpportunity: "None",
  saveFailed: "Couldn't save the task.",
  deleteConfirm: "Delete the task \"{title}\"?",
  loadFailed: "Couldn't load the tasks.",
  markDone: "Mark \"{title}\" as done",
  groups: {
    overdue: "Overdue",
    today: "Today",
    upcoming: "Upcoming",
    undated: "No date",
    done: "Done",
  },
  show: "Show",
  pending: "Pending",
  mine: "Mine",
  nonePending: "No pending tasks.",
  noneDone: "No tasks done yet.",
  noneForContact: "This contact has no pending tasks.",
};
