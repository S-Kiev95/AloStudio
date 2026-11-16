import type { settingsBots as es } from "../es/settingsBots";
import type { Strings } from "../types";

export const settingsBots: Strings<typeof es> = {
  deleteConfirm: "Excluir o bot \"{name}\"?",
  saveFailed: "Não foi possível salvar o bot.",
  outgoingUrl: "URL de saída",
  outgoingUrlHint: "O backend vai enviar os eventos de mensagem para esta URL.",
  create: "Criar bot",
  new: "Novo bot",
  edit: "Editar bot",
  loadFailed: "Não foi possível carregar os bots.",
  empty: "Ainda não há bots.",
  secret: "Secret:",
  rotateSecret: "Rotacionar secret",
  rotateFailed: "Não foi possível rotacionar o secret.",
};
