import type { hc as es } from "../es/hc";
import type { Strings } from "../types";

export const hc: Strings<typeof es> = {
  articleEmpty: "Dieser Artikel hat noch keinen Inhalt.",
  categoryEmpty: "In dieser Kategorie gibt es noch keine veröffentlichten Artikel.",
  errorTitle: "Das Hilfecenter konnte nicht geladen werden",
  errorBody: "Lade die Seite gleich noch einmal.",
  notFoundTitle: "Dieser Artikel wurde nicht gefunden",
  notFoundBody: "Vielleicht ist er nicht mehr veröffentlicht oder der Link hat sich geändert.",
  categories: "Kategorien",
  recentArticles: "Neueste Artikel",
  noArticles: "Noch keine veröffentlichten Artikel.",
  backToSite: "Zurück zur Website",
  poweredBy: "Bereitgestellt von AloStudio",
};
