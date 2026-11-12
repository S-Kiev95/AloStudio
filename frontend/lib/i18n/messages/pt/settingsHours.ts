import type { settingsHours as es } from "../es/settingsHours";
import type { Strings } from "../types";

export const settingsHours: Strings<typeof es> = {
  saveFailed: "Não foi possível salvar o horário.",
  loading: "Carregando horário…",
  loadFailed: "Não foi possível carregar o horário.",
  weekly: "Horário semanal",
  closed: "Fechado",
  allDay: "24 horas",
  opens: "Abre",
  closes: "Fecha",
  inboxesLoadFailed: "Não foi possível carregar as caixas de entrada.",
  noInboxes: "Ainda não há caixas de entrada conectadas.",
};
