import type { settingsSecurity as es } from "../es/settingsSecurity";
import type { Strings } from "../types";

export const settingsSecurity: Strings<typeof es> = {
  fillAll: "Fill in all three fields.",
  min8: "The new password must be at least 8 characters long.",
  mismatch: "The confirmation doesn't match the new password.",
  changeFailed: "Couldn't change the password.",
  changePassword: "Change password",
  updated: "Your password was updated.",
  current: "Current password",
  new: "New password",
  min8Short: "At least 8 characters.",
  repeat: "Repeat new password",
  update: "Update password",
};
