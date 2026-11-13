import type { settingsMacros as es } from "../es/settingsMacros";
import type { Strings } from "../types";

export const settingsMacros: Strings<typeof es> = {
  action: "Ação",
  noParams: "Sem parâmetros",
  params: "Parâmetros",
  removeAction: "Remover ação",
  back: "Voltar para macros",
  loadFailed: "Não foi possível carregar a macro.",
  needAction: "Adicione pelo menos uma ação.",
  saveFailed: "Não foi possível salvar a macro.",
  visibility: "Visibilidade",
  personal: "Pessoal",
  globalLong: "Global (visível para toda a conta)",
  actions: "Ações",
  needActionHint: "Adicione pelo menos uma ação para definir o que a macro faz.",
  addAction: "Adicionar ação",
  create: "Criar macro",
  new: "Nova macro",
  listLoadFailed: "Não foi possível carregar as macros.",
  empty: "Ainda não há macros.",
  global: "Global",
  deleteConfirm: "Excluir a macro \"{name}\"?",
  actionsOne: "{count} ação",
  actionsMany: "{count} ações",
  by: "por {name}",
};
