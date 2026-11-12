import type { agent as es } from "../es/agent";
import type { Strings } from "../types";

export const agent: Strings<typeof es> = {
  suggestions: {
    write: "Monte uma publicação para amanhã às 10 em todos os meus canais",
    week: "O que tenho agendado esta semana?",
    lastMonth: "Como foram minhas publicações no último mês?",
  },
  unconfigured: "O agente ainda não está configurado. Um operador da instalação precisa cadastrar a chave da OpenAI em Configurações → Instalação → Inteligência artificial.",
  readOnly: "Você pode consultar publicações e estatísticas. Criar ou excluir publicações é feito por um administrador.",
  greeting: "Olá, sou o agente do AloStudio. Posso montar e agendar publicações nos seus canais, revisar seu calendário e contar como foram seus posts.",
  seeInCalendar: "Ver no calendário",
  newChat: "Novo chat",
  chat: "Chat",
  chats: "Chats",
  statusFailed: "Não foi possível consultar o status do agente.",
  chatNotFound: "Este chat não foi encontrado.",
  chatLoadFailed: "Não foi possível carregar o chat.",
  thinking: "Pensando…",
  composer: {
    label: "Mensagem para o agente",
    unavailable: "O agente não está disponível",
    placeholder: "Escreva uma mensagem…",
    send: "Enviar mensagem",
  },
  deleteFailed: "Não foi possível excluir o chat.",
  closeList: "Fechar lista de chats",
  chatsLoadFailed: "Não foi possível carregar os chats.",
  noChats: "Você ainda não tem chats.",
  toConfirm: "A confirmar",
  deleteChat: "Excluir chat",
  pending: {
    seeLess: "Ver menos",
    seeMore: "Ver mais",
    changeHint: "Se quiser mudar algo, escreva e o agente monta uma nova proposta.",
    willDelete: "Esta publicação será excluída",
    soon: "Sai nos próximos minutos",
    at: "Sai {when}",
  },
  deleteConfirm: "Excluir o chat “{title}”?",
  deleteChatNamed: "Excluir chat {title}",
};
