import type { apiErrors as es } from "../es/apiErrors";
import type { Strings } from "../types";

export const apiErrors: Strings<typeof es> = {
  notAuthorized: "Vous n’avez pas l’autorisation de faire cela.",
  tooManyAttempts: "Trop de tentatives échouées. Attendez quelques minutes et réessayez.",
  mediaUnsupported: "Format non pris en charge. Téléversez une image ou une vidéo.",
  imageTooBig: "L’image dépasse la limite de 30 Mo.",
  videoTooBig: "La vidéo dépasse la limite de 200 Mo.",
  uploadFailed: "Impossible de téléverser le fichier ({status}).",
  pushDenied: "Autorisation des notifications refusée.",
  agentFailed: "Une erreur s’est produite en communiquant avec l’agent.",
  requestFailed: "Une erreur s’est produite lors du traitement de la demande.",
  requestFailedStatus: "La demande a échoué ({status}).",
};
