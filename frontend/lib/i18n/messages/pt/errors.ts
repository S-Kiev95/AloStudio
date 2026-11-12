import type { errors as es } from "../es/errors";
import type { Strings } from "../types";

export const errors: Strings<typeof es> = {
  sectionTitle: "Não conseguimos carregar esta seção",
  sectionBody: "Algo deu errado ao buscar os dados. Tente de novo em instantes.",
  accountNotFoundTitle: "Não encontramos o que você procura",
  accountNotFoundBody: "Este caminho não existe nesta conta.",
  noAccountsTitle: "Sem contas",
  noAccountsBody: "Seu usuário ainda não tem contas associadas.",
  pageTitle: "Algo deu errado",
  pageBody: "Tivemos um problema ao carregar esta página. Tente recarregar.",
  goHome: "Ir para o início",
  notFoundTitle: "Página não encontrada",
  notFoundBody: "A URL não existe ou o conteúdo não está mais disponível.",
};
