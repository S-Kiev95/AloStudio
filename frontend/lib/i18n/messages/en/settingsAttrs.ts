import type { settingsAttrs as es } from "../es/settingsAttrs";
import type { Strings } from "../types";

export const settingsAttrs: Strings<typeof es> = {
  displayNameRequired: "The display name is required.",
  saveFailed: "Couldn't save the attribute.",
  displayName: "Display name",
  appliesTo: "Applies to",
  regex: "Pattern (regex)",
  regexHint: "Hint for the user",
  regexHintPlaceholder: "E.g. ABC-1234",
  values: "Values",
  noValues: "There are no values in the list yet.",
  newValue: "New value",
  create: "Create attribute",
  new: "New attribute",
  edit: "Edit attribute",
  model: "Model",
  loadFailed: "Couldn't load the attributes.",
  empty: "No attributes defined yet.",
  deleteConfirm: "Delete \"{name}\"?",
  keyReadonly: "Key: {key} (not editable)",
  types: {
    text: "Text",
    number: "Number",
    currency: "Currency",
    percent: "Percentage",
    link: "Link",
    date: "Date",
    list: "List",
    checkbox: "Checkbox",
  },
};
