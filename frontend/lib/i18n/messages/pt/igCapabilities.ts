import type { igCapabilities as es } from "../es/igCapabilities";
import type { Strings } from "../types";

export const igCapabilities: Strings<typeof es> = {
  publish: "Publicar fotos, carrosséis, reels e stories",
  comments: "Ler e responder comentários, com regras automáticas",
  insights: "Métricas das publicações",
  facebook: {
    summary: "O caminho completo. É o indicado se você vai atender mensagens.",
    requirement: "Precisa de uma Página do Facebook vinculada à conta do Instagram.",
    dmsNote: "As mensagens chegam com texto e anexos.",
  },
  dms: "Receber e responder mensagens diretas",
  deletePosts: "Excluir publicações pelo AloStudio",
  instagram: {
    summary: "Mais simples de conectar, mas deixa as mensagens fora de serviço.",
    requirement: "Não precisa de Página do Facebook.",
    dmsNote: "A Meta avisa que chegou uma mensagem, mas não envia o texto, então a conversa não pode ser reconstruída. É uma limitação dela, não do AloStudio.",
    deleteNote: "A Meta não oferece a exclusão nesta API. É preciso excluir pelo app do Instagram.",
  },
};
