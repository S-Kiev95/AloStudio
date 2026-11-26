import type { businessProfile as es } from "../es/businessProfile";
import type { Strings } from "../types";

export const businessProfile: Strings<typeof es> = {
  title: "About the business",
  intro: "Describe once what the company does and how it works. Every AI agent of the account reads it: the one that answers calls, the one that classifies conversations and the one that replies by chat.",
  label: "Business description",
  placeholder: "What it sells or which services it offers, hours, address, how to pay, exchange and return policies, frequent questions, what not to do…",
  hint: "Prices and products are read from the catalogue and long answers from the Help Center: write here what is not in those places.",
  readOnly: "An administrator of the account edits it.",
  loading: "Loading…",
  loadFailed: "The description could not be loaded.",
  save: "Save",
  saved: "Saved.",
  saveFailed: "It could not be saved (up to 8,000 characters).",
};
