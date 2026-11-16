import type { settingsSecurity as es } from "../es/settingsSecurity";
import type { Strings } from "../types";

export const settingsSecurity: Strings<typeof es> = {
  fillAll: "Fülle alle drei Felder aus.",
  min8: "Das neue Passwort muss mindestens 8 Zeichen lang sein.",
  mismatch: "Die Bestätigung stimmt nicht mit dem neuen Passwort überein.",
  changeFailed: "Das Passwort konnte nicht geändert werden.",
  changePassword: "Passwort ändern",
  updated: "Dein Passwort wurde aktualisiert.",
  current: "Aktuelles Passwort",
  new: "Neues Passwort",
  min8Short: "Mindestens 8 Zeichen.",
  repeat: "Neues Passwort wiederholen",
  update: "Passwort aktualisieren",
};
