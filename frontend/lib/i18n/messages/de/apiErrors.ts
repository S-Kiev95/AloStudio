import type { apiErrors as es } from "../es/apiErrors";
import type { Strings } from "../types";

export const apiErrors: Strings<typeof es> = {
  notAuthorized: "Dazu hast du keine Berechtigung.",
  tooManyAttempts: "Zu viele fehlgeschlagene Versuche. Warte ein paar Minuten und versuch es erneut.",
  mediaUnsupported: "Format nicht unterstützt. Lade ein Bild oder ein Video hoch.",
  imageTooBig: "Das Bild überschreitet das Limit von 30 MB.",
  videoTooBig: "Das Video überschreitet das Limit von 200 MB.",
  uploadFailed: "Die Datei konnte nicht hochgeladen werden ({status}).",
  pushDenied: "Berechtigung für Benachrichtigungen verweigert.",
  agentFailed: "Bei der Kommunikation mit dem Agenten ist ein Fehler aufgetreten.",
  requestFailed: "Bei der Verarbeitung der Anfrage ist ein Fehler aufgetreten.",
  requestFailedStatus: "Die Anfrage ist fehlgeschlagen ({status}).",
};
