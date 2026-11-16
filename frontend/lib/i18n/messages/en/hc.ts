import type { hc as es } from "../es/hc";
import type { Strings } from "../types";

export const hc: Strings<typeof es> = {
  articleEmpty: "This article has no content yet.",
  categoryEmpty: "No published articles in this category yet.",
  errorTitle: "We couldn't load the Help Center",
  errorBody: "Try reloading in a moment.",
  notFoundTitle: "We couldn't find this article",
  notFoundBody: "It may no longer be published, or the link may have changed.",
  categories: "Categories",
  recentArticles: "Recent articles",
  noArticles: "No published articles yet.",
  backToSite: "Back to the site",
  poweredBy: "Powered by AloStudio",
};
