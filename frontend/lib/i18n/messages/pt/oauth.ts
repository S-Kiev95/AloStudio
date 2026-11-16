import type { oauth as es } from "../es/oauth";
import type { Strings } from "../types";

export const oauth: Strings<typeof es> = {
  scope: {
    readPosts: "Ver suas publicações, canais e estatísticas",
    readConversations: "Ver conversas e contatos",
    writePosts: "Agendar e excluir publicações",
    writeConversations: "Responder e organizar conversas",
  },
  cannotAuthorize: "Não é possível autorizar",
  invalidRequest: "O pedido do app não é válido.",
  backToApp: "Voltar ao AloStudio",
  createdBy: "Criado por",
  willBeAbleTo: "Vai poder:",
  whichAccount: "Em qual conta?",
  roleNotAllowed: "Sua função nesta conta não permite dar esse acesso",
  sendFailed: "Não foi possível enviar sua resposta.",
  authorize: "Autorizar",
  wantsAccess: "{app} quer acessar sua conta do AloStudio",
  redirectNote: "Você será levado para {host}. Você pode remover o acesso quando quiser em Configurações → Apps OAuth.",
};
