import type { settingsSets as es } from "../es/settingsSets";
import type { Strings } from "../types";

export const settingsSets: Strings<typeof es> = {
  title: "Sets ({count})",
  channelsLabel: "Channels: {names}",
  deleteFailed: "Couldn't delete the set.",
  intro: "Manage your content sets to reuse them easily in your posts.",
  add: "Add set",
  loadFailed: "Couldn't load the sets.",
  empty: "No sets saved yet.",
  noChannels: "No channels",
  edit: "Edit set",
  delete: "Delete set",
};
