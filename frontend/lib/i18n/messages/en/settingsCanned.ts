import type { settingsCanned as es } from "../es/settingsCanned";
import type { Strings } from "../types";

export const settingsCanned: Strings<typeof es> = {
  shortCodeRequired: "The short code is required.",
  contentRequired: "The content is required.",
  saveFailed: "Couldn't save the response.",
  shortCode: "Short code",
  content: "Content",
  create: "Create response",
  new: "New response",
  search: "Search responses",
  searchPlaceholder: "Search by short code or content…",
  edit: "Edit response",
  loadFailed: "Couldn't load the responses.",
  noneFound: "No responses found.",
  empty: "No responses yet.",
  deleteConfirm: "Delete \"/{code}\"?",
  shortCodeHint: "Type {code} in the editor to insert the response.",
  shortCodeExample: "shortcut",
};
