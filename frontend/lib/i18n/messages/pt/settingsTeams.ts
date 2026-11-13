import type { settingsTeams as es } from "../es/settingsTeams";
import type { Strings } from "../types";

export const settingsTeams: Strings<typeof es> = {
  back: "Voltar para equipes",
  loadFailed: "Não foi possível carregar a equipe.",
  saveFailed: "Não foi possível salvar a equipe.",
  autoAssign: "Permitir atribuição automática",
  create: "Criar equipe",
  addMemberFailed: "Não foi possível adicionar o membro.",
  removeMemberFailed: "Não foi possível remover o membro.",
  members: "Membros",
  addMember: "Adicionar membro",
  availableAgents: "Agentes disponíveis",
  allMembers: "Todos os agentes já são membros desta equipe.",
  loadingMembers: "Carregando membros…",
  membersLoadFailed: "Não foi possível carregar os membros.",
  noMembers: "A equipe não tem membros.",
  removeFromTeam: "Remover da equipe",
  new: "Nova equipe",
  listLoadFailed: "Não foi possível carregar as equipes.",
  empty: "Ainda não há equipes.",
  youAreMember: "Você é membro",
  noAutoAssign: "Sem atribuição automática",
  deleteConfirm: "Excluir a equipe \"{name}\"?",
  removeConfirm: "Remover {name} da equipe?",
};
