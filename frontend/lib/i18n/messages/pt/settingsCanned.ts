import type { settingsCanned as es } from "../es/settingsCanned";
import type { Strings } from "../types";

export const settingsCanned: Strings<typeof es> = {
  shortCodeRequired: "O atalho é obrigatório.",
  contentRequired: "O conteúdo é obrigatório.",
  saveFailed: "Não foi possível salvar a resposta.",
  shortCode: "Atalho",
  content: "Conteúdo",
  create: "Criar resposta",
  new: "Nova resposta",
  search: "Buscar respostas",
  searchPlaceholder: "Buscar por atalho ou conteúdo…",
  edit: "Editar resposta",
  loadFailed: "Não foi possível carregar as respostas.",
  noneFound: "Nenhuma resposta encontrada.",
  empty: "Ainda não há respostas.",
  deleteConfirm: "Excluir \"/{code}\"?",
  shortCodeHint: "Digite {code} no editor para inserir a resposta.",
  shortCodeExample: "atalho",
};
