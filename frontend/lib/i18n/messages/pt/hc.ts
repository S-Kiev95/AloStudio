import type { hc as es } from "../es/hc";
import type { Strings } from "../types";

export const hc: Strings<typeof es> = {
  articleEmpty: "Este artigo ainda não tem conteúdo.",
  categoryEmpty: "Ainda não há artigos publicados nesta categoria.",
  errorTitle: "Não conseguimos carregar a Central de ajuda",
  errorBody: "Tente recarregar em instantes.",
  notFoundTitle: "Não encontramos este artigo",
  notFoundBody: "Talvez não esteja mais publicado ou o link tenha mudado.",
  categories: "Categorias",
  recentArticles: "Artigos recentes",
  noArticles: "Ainda não há artigos publicados.",
  backToSite: "Voltar ao site",
  poweredBy: "Feito com AloStudio",
};
