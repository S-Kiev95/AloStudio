import type { settingsPlugs as es } from "../es/settingsPlugs";
import type { Strings } from "../types";

export const settingsPlugs: Strings<typeof es> = {
  messageTooLong: "A mensagem passa do máximo de {max} caracteres ({count}/{max}).",
  channelPlugs: "Plugs de {name}",
  whenLikes: "Quando chegar a {n} curtidas",
  channelRequired: "Escolha um canal para configurar o plug.",
  actionRequired: "Escolha uma ação do catálogo.",
  thresholdMin: "O limite deve ser de pelo menos 1 curtida.",
  messageRequired: "Escreva a mensagem para esta ação.",
  saveFailed: "Não foi possível salvar o plug.",
  updateFailed: "Não foi possível atualizar o plug.",
  deleteFailed: "Não foi possível excluir o plug.",
  title: "Plugs",
  intro: "Execute ações automáticas nas suas publicações quando atingirem um limite de curtidas.",
  loadFailed: "Não foi possível carregar os plugs.",
  connectThreads: "Conecte o Threads para usar ações automáticas",
  noChannels: "Não há canais conectados com ações disponíveis no catálogo.",
  goToCalendar: "Ir ao calendário para conectar canais",
  add: "Adicionar plug",
  noneInChannel: "Não há ações automáticas configuradas neste canal.",
  edit: "Editar plug",
  delete: "Excluir plug",
  lastRuns: "Últimas execuções",
  runOk: "OK",
  runFailed: "Falhou",
  channel: "Canal",
  thresholdLabel: "Quando chegar a N curtidas",
  message: "Mensagem",
  messagePlaceholder: "Escreva a resposta automática…",
  save: "Salvar plug",
  kinds: {
    reply_after_likes: {
      label: "Responder ao chegar a N curtidas",
      description: "Quando um post chega a essa quantidade de curtidas, publica sua mensagem como resposta a esse mesmo post (por exemplo, um link ou uma oferta).",
    },
    repost_after_likes: {
      label: "Repostar ao chegar a N curtidas",
      description: "Quando um post chega a essa quantidade de curtidas, ele é repostado no seu perfil para que seus seguidores o vejam de novo.",
    },
  },
};
