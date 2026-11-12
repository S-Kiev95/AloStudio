import type { settingsAttrs as es } from "../es/settingsAttrs";
import type { Strings } from "../types";

export const settingsAttrs: Strings<typeof es> = {
  displayNameRequired: "O nome de exibição é obrigatório.",
  saveFailed: "Não foi possível salvar o atributo.",
  displayName: "Nome de exibição",
  appliesTo: "Aplica-se a",
  regex: "Padrão (regex)",
  regexHint: "Dica para o usuário",
  regexHintPlaceholder: "Ex.: ABC-1234",
  values: "Valores",
  noValues: "Ainda não há valores na lista.",
  newValue: "Novo valor",
  create: "Criar atributo",
  new: "Novo atributo",
  edit: "Editar atributo",
  model: "Modelo",
  loadFailed: "Não foi possível carregar os atributos.",
  empty: "Ainda não há atributos definidos.",
  deleteConfirm: "Excluir \"{name}\"?",
  keyReadonly: "Chave: {key} (não editável)",
  types: {
    text: "Texto",
    number: "Número",
    currency: "Moeda",
    percent: "Porcentagem",
    link: "Link",
    date: "Data",
    list: "Lista",
    checkbox: "Caixa de seleção",
  },
};
