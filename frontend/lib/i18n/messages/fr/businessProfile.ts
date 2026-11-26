import type { businessProfile as es } from "../es/businessProfile";
import type { Strings } from "../types";

export const businessProfile: Strings<typeof es> = {
  title: "À propos de l'entreprise",
  intro: "Décrivez une seule fois ce que fait l'entreprise et comment elle travaille. Tous les agents IA du compte le lisent : celui qui répond aux appels, celui qui classe les conversations et celui qui répond par chat.",
  label: "Description de l'entreprise",
  placeholder: "Ce qu'elle vend ou les services proposés, horaires, adresse, moyens de paiement, politique d'échange et de retour, questions fréquentes, ce qu'il ne faut pas faire…",
  hint: "Les prix et les produits sont lus dans le catalogue et les réponses longues dans le Centre d'aide : écrivez ici ce qui n'y est pas.",
  readOnly: "Un administrateur du compte le modifie.",
  loading: "Chargement…",
  loadFailed: "Impossible de charger la description.",
  save: "Enregistrer",
  saved: "Enregistré.",
  saveFailed: "Impossible d'enregistrer (8 000 caractères maximum).",
};
