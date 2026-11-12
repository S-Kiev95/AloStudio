import type { settingsMacros as es } from "../es/settingsMacros";
import type { Strings } from "../types";

export const settingsMacros: Strings<typeof es> = {
  action: "Action",
  noParams: "No parameters",
  params: "Parameters",
  removeAction: "Remove action",
  back: "Back to macros",
  loadFailed: "Couldn't load the macro.",
  needAction: "Add at least one action.",
  saveFailed: "Couldn't save the macro.",
  visibility: "Visibility",
  personal: "Personal",
  globalLong: "Global (visible to the whole account)",
  actions: "Actions",
  needActionHint: "Add at least one action to define what the macro does.",
  addAction: "Add action",
  create: "Create macro",
  new: "New macro",
  listLoadFailed: "Couldn't load the macros.",
  empty: "No macros yet.",
  global: "Global",
  deleteConfirm: "Delete the macro \"{name}\"?",
  actionsOne: "{count} action",
  actionsMany: "{count} actions",
  by: "by {name}",
};
