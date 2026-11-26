import type { businessProfile as es } from "../es/businessProfile";
import type { Strings } from "../types";

export const businessProfile: Strings<typeof es> = {
  title: "Sobre o negócio",
  intro: "Conte uma única vez o que a empresa faz e como trabalha. Todos os agentes de IA da conta leem: o que atende ligações, o que classifica conversas e o que responde por chat.",
  label: "Descrição do negócio",
  placeholder: "O que vende ou que serviços oferece, horários, endereço, formas de pagamento, políticas de troca e devolução, perguntas frequentes, o que não fazer…",
  hint: "Preços e produtos são lidos do catálogo e as respostas longas da Central de ajuda: aqui vai o que não está nesses lugares.",
  readOnly: "Quem edita é um administrador da conta.",
  loading: "Carregando…",
  loadFailed: "Não foi possível carregar a descrição.",
  save: "Salvar",
  saved: "Salvo.",
  saveFailed: "Não foi possível salvar (até 8.000 caracteres).",
};
