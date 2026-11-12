import type { products as es } from "../es/products";
import type { Strings } from "../types";

export const products: Strings<typeof es> = {
  form: {
    nameRequired: "Le nom est obligatoire.",
    priceInvalid: "Le prix n’est pas valide.",
    saveFailed: "Impossible d’enregistrer le produit.",
    description: "Description",
    price: "Prix",
    currency: "Devise",
    productUrl: "URL du produit",
    imageUrl: "URL de l’image",
    active: "Actif (visible dans le catalogue)",
    create: "Créer le produit",
  },
  filters: {
    all: "Tous",
    active: "Actifs",
    inactive: "Inactifs",
  },
  title: "Produits",
  new: "Nouveau produit",
  edit: "Modifier le produit",
  filterLabel: "Filtrer les produits",
  loadFailed: "Impossible de charger les produits.",
  empty: "Aucun produit pour l’instant.",
  active: "Actif",
  inactive: "Inactif",
  deleteConfirm: "Supprimer « {name} » ?",
  description: "Description",
};
