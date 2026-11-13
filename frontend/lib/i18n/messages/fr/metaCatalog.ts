import type { metaCatalog as es } from "../es/metaCatalog";
import type { Strings } from "../types";

export const metaCatalog: Strings<typeof es> = {
  title: "Catalogue Meta",
  intro: "Connectez un catalogue Commerce Manager et les produits actifs y sont envoyés, prêts à s’afficher sur WhatsApp, Instagram et Facebook.",
  howTo: "L’ID se trouve dans Commerce Manager → votre catalogue → Paramètres. Le jeton est celui d’un utilisateur système (Paramètres de l’entreprise → Utilisateurs système) avec l’autorisation catalog_management et l’accès au catalogue.",
  catalogId: "ID du catalogue",
  token: "Jeton d’accès",
  tokenKeep: "Laissez vide pour garder l’actuel",
  connect: "Connecter le catalogue",
  disconnect: "Déconnecter",
  syncNow: "Synchroniser",
  disconnectConfirm: "Déconnecter le catalogue ? Les produits déjà chez Meta y restent.",
  unnamed: "Catalogue sans nom",
  neverSynced: "Pas encore synchronisé.",
  lastSync: "Dernière synchronisation : {date} · {sent} envoyés, {failed} avec des problèmes",
  stillChecking: "Meta vérifiait encore l’envoi ; ce qui échoue apparaîtra à la prochaine synchronisation.",
  autoSync: "Chaque modification d’un produit est envoyée automatiquement, quelques secondes plus tard.",
  synced: "Terminé : {sent} envoyés, {removed} retirés, {skipped} incomplets, {failed} refusés par Meta.",
  state: {
    synced: "Chez Meta",
    pending: "Pas envoyé à Meta",
    missing: "Non envoyé à Meta, il manque : {fields}",
    refused: "Refusé par Meta",
  },
  fields: {
    description: "description",
    price: "prix et devise",
    url: "lien",
    image_url: "image",
  },
  errors: {
    token: "Meta n’a pas accepté le jeton : vérifiez qu’il est valide et non expiré.",
    permission: "Le jeton n’a pas d’autorisation sur ce catalogue (catalog_management).",
    catalog_id: "L’ID du catalogue ne contient que des chiffres.",
    refused: "Meta a refusé la demande.",
    unreachable: "Impossible de joindre Meta. Réessayez plus tard.",
    not_connected: "Connectez d’abord un catalogue.",
  },
};
