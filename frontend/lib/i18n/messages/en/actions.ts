import type { actions as es } from "../es/actions";
import type { Strings } from "../types";

export const actions: Strings<typeof es> = {
  apply: "Apply",
  cancel: "Cancel",
  selectPlaceholder: "Select…",
  edit: "Edit",
  clear: "Clear",
  previous: "Previous",
  next: "Next",
  addPlaceholder: "Add…",
  back: "Back",
  send: "Send",
  close: "Close",
  retry: "Retry",
  discard: "Discard",
  yes: "Yes",
  no: "No",
  page: "Page {n}",
};
