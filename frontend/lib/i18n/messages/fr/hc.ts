import type { hc as es } from "../es/hc";
import type { Strings } from "../types";

export const hc: Strings<typeof es> = {
  articleEmpty: "Cet article n’a pas encore de contenu.",
  categoryEmpty: "Aucun article publié dans cette catégorie pour l’instant.",
  errorTitle: "Impossible de charger le centre d’aide",
  errorBody: "Essayez de recharger dans un instant.",
  notFoundTitle: "Article introuvable",
  notFoundBody: "Il n’est peut-être plus publié, ou le lien a changé.",
  categories: "Catégories",
  recentArticles: "Articles récents",
  noArticles: "Aucun article publié pour l’instant.",
  backToSite: "Retour au site",
  poweredBy: "Propulsé par AloStudio",
};
