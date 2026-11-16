import type { settingsSecurity as es } from "../es/settingsSecurity";
import type { Strings } from "../types";

export const settingsSecurity: Strings<typeof es> = {
  fillAll: "Preencha os três campos.",
  min8: "A nova senha precisa ter pelo menos 8 caracteres.",
  mismatch: "A confirmação não coincide com a nova senha.",
  changeFailed: "Não foi possível alterar a senha.",
  changePassword: "Alterar senha",
  updated: "Sua senha foi atualizada.",
  current: "Senha atual",
  new: "Nova senha",
  min8Short: "Mínimo de 8 caracteres.",
  repeat: "Repetir nova senha",
  update: "Atualizar senha",
};
