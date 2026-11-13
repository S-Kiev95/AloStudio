import type { settingsSets as es } from "../es/settingsSets";
import type { Strings } from "../types";

export const settingsSets: Strings<typeof es> = {
  title: "Sets ({count})",
  channelsLabel: "Canais: {names}",
  deleteFailed: "Não foi possível excluir o set.",
  intro: "Gerencie seus sets de conteúdo para reutilizá-los facilmente nas suas publicações.",
  add: "Adicionar set",
  loadFailed: "Não foi possível carregar os sets.",
  empty: "Ainda não há sets salvos.",
  noChannels: "Sem canais",
  edit: "Editar set",
  delete: "Excluir set",
};
