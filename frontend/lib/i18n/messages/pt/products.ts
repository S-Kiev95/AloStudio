import type { products as es } from "../es/products";
import type { Strings } from "../types";

export const products: Strings<typeof es> = {
  form: {
    nameRequired: "O nome é obrigatório.",
    priceInvalid: "O preço não é válido.",
    saveFailed: "Não foi possível salvar o produto.",
    description: "Descrição",
    price: "Preço",
    currency: "Moeda",
    productUrl: "URL do produto",
    imageUrl: "URL da imagem",
    active: "Ativo (visível no catálogo)",
    create: "Criar produto",
  },
  filters: {
    all: "Todos",
    active: "Ativos",
    inactive: "Inativos",
  },
  title: "Produtos",
  new: "Novo produto",
  edit: "Editar produto",
  filterLabel: "Filtrar produtos",
  loadFailed: "Não foi possível carregar os produtos.",
  empty: "Nenhum produto ainda.",
  active: "Ativo",
  inactive: "Inativo",
  deleteConfirm: "Excluir \"{name}\"?",
  description: "Descrição",
};
