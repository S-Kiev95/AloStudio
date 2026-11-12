import type { errors as es } from "../es/errors";
import type { Strings } from "../types";

export const errors: Strings<typeof es> = {
  sectionTitle: "We couldn't load this section",
  sectionBody: "Something went wrong fetching the data. Try again in a moment.",
  accountNotFoundTitle: "We couldn't find what you're looking for",
  accountNotFoundBody: "This path doesn't exist in this account.",
  noAccountsTitle: "No accounts",
  noAccountsBody: "Your user isn't linked to any account yet.",
  pageTitle: "Something went wrong",
  pageBody: "We had a problem loading this page. Try reloading.",
  goHome: "Go home",
  notFoundTitle: "Page not found",
  notFoundBody: "The URL doesn't exist or the content is no longer available.",
};
