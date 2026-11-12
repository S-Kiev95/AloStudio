import type { settingsAgents as es } from "../es/settingsAgents";
import type { Strings } from "../types";

export const settingsAgents: Strings<typeof es> = {
  nameEmailRequired: "O nome e o email são obrigatórios.",
  inviteFailed: "Não foi possível enviar o convite.",
  invite: "Convidar agente",
  role: "Função",
  roles: {
    agent: "Agente",
    administrator: "Administrador",
  },
  inviteNote: "A pessoa vai receber um email com um link para definir a senha.",
  sendInvite: "Enviar convite",
  loadFailed: "Não foi possível carregar os agentes.",
  empty: "Ainda não há agentes nesta conta.",
  roleFailed: "Não foi possível alterar a função.",
  removeFromAccount: "Remover da conta",
  removeConfirm: "Remover {name} da conta?",
  removeNamed: "Remover {name}",
  invited: "Enviamos um convite para {email}. O link expira quando a senha for definida.",
};
