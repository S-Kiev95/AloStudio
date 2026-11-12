import type { settingsMcp as es } from "../es/settingsMcp";
import type { Strings } from "../types";

export const settingsMcp: Strings<typeof es> = {
  rotateConfirm: "Renouveler le jeton « {name} » ? Les clients qui utilisent l’actuel échoueront immédiatement.",
  deleteConfirm: "Supprimer le jeton « {name} » ?",
  lastUsed: "Dernière utilisation {when}",
  new: "Nouveau jeton",
  intro: "Utilisez ces jetons pour automatiser votre compte et connecter l’agent IA, n8n, la CLI ou d’autres outils externes à AloStudio via l’API et le serveur MCP. Chaque jeton est associé à ce compte avec une portée lecture, écriture ou administration.",
  edit: "Modifier le jeton",
  loadFailed: "Impossible de charger les jetons. Votre compte est-il administrateur ?",
  empty: "Aucun jeton pour l’instant.",
  rotateFailed: "Impossible de renouveler.",
  neverUsed: "Jamais utilisé",
  saveNow: "Enregistrez-le maintenant",
  shownOnce: "Ce jeton n’est affiché qu’une seule fois. Si vous le perdez, vous devrez le renouveler pour en générer un nouveau.",
  copied: "Copié",
  copy: "Copier",
  saveFailed: "Impossible d’enregistrer le jeton.",
  namePlaceholder: "Ex. agent-support",
  permissions: "Autorisations",
  generate: "Générer le jeton",
};
