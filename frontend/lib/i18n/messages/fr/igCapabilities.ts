import type { igCapabilities as es } from "../es/igCapabilities";
import type { Strings } from "../types";

export const igCapabilities: Strings<typeof es> = {
  publish: "Publier des photos, carrousels, reels et stories",
  comments: "Lire et répondre aux commentaires, avec des règles automatiques",
  insights: "Statistiques des publications",
  facebook: {
    summary: "Le parcours complet. C’est celui à choisir si vous gérez des messages.",
    requirement: "Nécessite une Page Facebook liée au compte Instagram.",
    dmsNote: "Les messages arrivent avec leur texte et leurs pièces jointes.",
  },
  dms: "Recevoir et répondre aux messages privés",
  deletePosts: "Supprimer des publications depuis AloStudio",
  instagram: {
    summary: "Plus simple à connecter, mais les messages ne fonctionnent pas.",
    requirement: "Pas besoin de Page Facebook.",
    dmsNote: "Meta signale qu’un message est arrivé mais n’envoie pas le texte, donc la conversation ne peut pas être reconstituée. C’est une limite de Meta, pas d’AloStudio.",
    deleteNote: "Meta ne propose pas la suppression dans cette API. Il faut supprimer depuis l’app Instagram.",
  },
};
