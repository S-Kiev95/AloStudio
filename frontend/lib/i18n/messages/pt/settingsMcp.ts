import type { settingsMcp as es } from "../es/settingsMcp";
import type { Strings } from "../types";

export const settingsMcp: Strings<typeof es> = {
  rotateConfirm: "Rotacionar o token \"{name}\"? Os clientes que usam o atual vão falhar imediatamente.",
  deleteConfirm: "Excluir o token \"{name}\"?",
  lastUsed: "Usado pela última vez {when}",
  new: "Novo token",
  intro: "Use estes tokens para automatizar sua conta e conectar o agente de IA, o n8n, a CLI ou outras ferramentas externas ao AloStudio pela API e pelo servidor MCP. Cada token fica associado a esta conta com escopo de leitura, escrita ou administração.",
  edit: "Editar token",
  loadFailed: "Não foi possível carregar os tokens. Sua conta é de administrador?",
  empty: "Ainda não há tokens.",
  rotateFailed: "Não foi possível rotacionar.",
  neverUsed: "Nunca usado",
  saveNow: "Guarde agora",
  shownOnce: "Este token só é mostrado uma vez. Se perdê-lo, terá que rotacioná-lo para gerar um novo.",
  copied: "Copiado",
  copy: "Copiar",
  saveFailed: "Não foi possível salvar o token.",
  namePlaceholder: "Ex.: agente-suporte",
  permissions: "Permissões",
  generate: "Gerar token",
  scopes: {
    read: "Leitura",
    write: "Escrita",
    admin: "Admin",
  },
  scopeHints: {
    read: "Só pode ler conversas, contatos, posts etc.",
    write: "Pode criar e modificar (responder, etiquetar, publicar).",
    admin: "Acesso completo, igual a um administrador.",
  },
};
