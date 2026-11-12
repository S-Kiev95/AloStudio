import type { settingsInstall as es } from "../es/settingsInstall";
import type { Strings } from "../types";

export const settingsInstall: Strings<typeof es> = {
  configuredCount: "{done}/{total} configurados",
  netConfigured: "configurada",
  netNotConfigured: "não configurada",
  operatorOnly: "Só o operador da instalação pode ver esta tela. Peça acesso a quem a implantou.",
  loadFailed: "Não foi possível carregar a configuração.",
  intro: "Ajustes que valem para todo o AloStudio, não para uma conta. Você pode deixá-los vazios e preenchê-los quando tiver as credenciais — o app funciona sem eles, e cada função avisa o que está faltando.",
  network: "Rede",
  clearFailed: "Não foi possível apagar.",
  notConfigured: "Não configurado",
  configured: "Configurado",
  savedHere: "salvo por aqui",
  resetToServer: "voltar ao valor do servidor",
  fromEnv: "vem do arquivo do servidor (.env)",
};
