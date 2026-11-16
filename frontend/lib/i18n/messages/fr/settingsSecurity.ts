import type { settingsSecurity as es } from "../es/settingsSecurity";
import type { Strings } from "../types";

export const settingsSecurity: Strings<typeof es> = {
  fillAll: "Remplissez les trois champs.",
  min8: "Le nouveau mot de passe doit contenir au moins 8 caractères.",
  mismatch: "La confirmation ne correspond pas au nouveau mot de passe.",
  changeFailed: "Impossible de changer le mot de passe.",
  changePassword: "Changer le mot de passe",
  updated: "Votre mot de passe a été mis à jour.",
  current: "Mot de passe actuel",
  new: "Nouveau mot de passe",
  min8Short: "8 caractères minimum.",
  repeat: "Répéter le nouveau mot de passe",
  update: "Mettre à jour le mot de passe",
};
