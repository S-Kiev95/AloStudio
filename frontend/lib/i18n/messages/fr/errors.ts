import type { errors as es } from "../es/errors";
import type { Strings } from "../types";

export const errors: Strings<typeof es> = {
  sectionTitle: "Impossible de charger cette section",
  sectionBody: "Un problème est survenu lors du chargement des données. Réessayez dans un instant.",
  accountNotFoundTitle: "Nous n’avons pas trouvé ce que vous cherchez",
  accountNotFoundBody: "Ce chemin n’existe pas dans ce compte.",
  noAccountsTitle: "Aucun compte",
  noAccountsBody: "Votre utilisateur n’est encore associé à aucun compte.",
  pageTitle: "Un problème est survenu",
  pageBody: "Nous n’avons pas pu charger cette page. Essayez de recharger.",
  goHome: "Aller à l’accueil",
  notFoundTitle: "Page introuvable",
  notFoundBody: "L’URL n’existe pas ou le contenu n’est plus disponible.",
};
