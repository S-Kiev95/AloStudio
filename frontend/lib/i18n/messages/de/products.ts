import type { products as es } from "../es/products";
import type { Strings } from "../types";

export const products: Strings<typeof es> = {
  form: {
    nameRequired: "Der Name ist erforderlich.",
    priceInvalid: "Der Preis ist ungültig.",
    saveFailed: "Das Produkt konnte nicht gespeichert werden.",
    description: "Beschreibung",
    price: "Preis",
    currency: "Währung",
    productUrl: "Produkt-URL",
    imageUrl: "Bild-URL",
    active: "Aktiv (im Katalog sichtbar)",
    create: "Produkt anlegen",
  },
  filters: {
    all: "Alle",
    active: "Aktiv",
    inactive: "Inaktiv",
  },
  title: "Produkte",
  new: "Neues Produkt",
  edit: "Produkt bearbeiten",
  filterLabel: "Produkte filtern",
  loadFailed: "Die Produkte konnten nicht geladen werden.",
  empty: "Noch keine Produkte.",
  active: "Aktiv",
  inactive: "Inaktiv",
  deleteConfirm: "„{name}“ löschen?",
};
