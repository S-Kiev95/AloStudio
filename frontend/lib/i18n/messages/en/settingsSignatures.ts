import type { settingsSignatures as es } from "../es/settingsSignatures";
import type { Strings } from "../types";

export const settingsSignatures: Strings<typeof es> = {
  tooLong: "The signature can't be longer than {max} characters.",
  textRequired: "Write the signature text.",
  saveFailed: "Couldn't save the signature.",
  updateFailed: "Couldn't update the signature.",
  deleteFailed: "Couldn't delete the signature.",
  title: "Signatures",
  intro: "You can add signatures to your account to reuse them in your posts or add one automatically to every new post.",
  add: "Add signature",
  loadFailed: "Couldn't load the signatures.",
  empty: "No signatures yet.",
  auto: "Automatic",
  unsetAuto: "Remove automatic",
  setAuto: "Make automatic",
  edit: "Edit signature",
  delete: "Delete signature",
  text: "Signature text",
  textPlaceholder: "E.g. Message us directly or visit our website.",
  autoQuestion: "Add it automatically to every new post?",
  save: "Save signature",
};
