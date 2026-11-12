import type { settingsSignatures as es } from "../es/settingsSignatures";
import type { Strings } from "../types";

export const settingsSignatures: Strings<typeof es> = {
  tooLong: "A assinatura não pode passar de {max} caracteres.",
  textRequired: "Escreva o texto da assinatura.",
  saveFailed: "Não foi possível salvar a assinatura.",
  updateFailed: "Não foi possível atualizar a assinatura.",
  deleteFailed: "Não foi possível excluir a assinatura.",
  title: "Assinaturas",
  intro: "Você pode adicionar assinaturas à sua conta para reutilizá-las nas publicações ou acrescentar uma automaticamente a cada nova publicação.",
  add: "Adicionar assinatura",
  loadFailed: "Não foi possível carregar as assinaturas.",
  empty: "Ainda não há assinaturas.",
  auto: "Automática",
  unsetAuto: "Remover automática",
  setAuto: "Tornar automática",
  edit: "Editar assinatura",
  delete: "Excluir assinatura",
  text: "Texto da assinatura",
  textPlaceholder: "Ex.: Fale com a gente por mensagem direta ou no nosso site.",
  autoQuestion: "Adicionar sozinha a cada nova publicação?",
  save: "Salvar assinatura",
};
