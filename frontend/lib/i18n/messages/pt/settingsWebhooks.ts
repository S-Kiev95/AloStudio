import type { settingsWebhooks as es } from "../es/settingsWebhooks";
import type { Strings } from "../types";

export const settingsWebhooks: Strings<typeof es> = {
  urlRequired: "A URL é obrigatória.",
  eventsRequired: "Escolha pelo menos um evento para assinar.",
  saveFailed: "Não foi possível salvar o webhook.",
  url: "URL",
  inboxOptional: "Caixa de entrada (opcional)",
  events: "Eventos assinados",
  create: "Criar webhook",
  new: "Novo webhook",
  edit: "Editar webhook",
  loadFailed: "Não foi possível carregar os webhooks.",
  empty: "Ainda não há webhooks.",
  deleteConfirm: "Excluir este webhook?",
  eventsOne: "{count} evento",
  eventsMany: "{count} eventos",
};
