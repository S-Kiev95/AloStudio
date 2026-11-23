import type { overview as es } from "../es/overview";
import type { Strings } from "../types";

export const overview: Strings<typeof es> = {
  live: {
    open: "Ouvertes",
    unattended: "Sans réponse",
    unassigned: "Non attribuées",
    pending: "En attente",
  },
  shortcut: {
    conversations: "Boîte de réception",
    conversationsDesc: "Messages de vos canaux",
    instagramDesc: "DM, publications et commentaires",
    campaigns: "Campagnes",
    campaignsDesc: "Envois et modèles",
    reports: "Rapports",
    reportsDesc: "Indicateurs et exports",
  },
  welcome: "Bienvenue",
  welcomeNamed: "Bonjour, {name}",
  intro: "Tous vos canaux, conversations et rendez-vous au même endroit. Voici où en sont les choses maintenant et sur les 7 derniers jours.",
  openInbox: "Ouvrir la boîte de réception",
  goCalendar: "Aller au calendrier",
  rightNow: "En ce moment",
  last7: "7 derniers jours",
  liveFailed: "Impossible de charger l'état en direct.",
  metricsFailed: "Impossible de charger les indicateurs de la période.",
  chartFailed: "Impossible de charger le graphique des conversations.",
  conversations: "Conversations",
  shortcuts: "Accès rapides",
};
