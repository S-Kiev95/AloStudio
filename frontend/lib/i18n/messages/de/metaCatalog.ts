import type { metaCatalog as es } from "../es/metaCatalog";
import type { Strings } from "../types";

export const metaCatalog: Strings<typeof es> = {
  title: "Meta-Katalog",
  intro: "Verbinde einen Commerce-Manager-Katalog, und aktive Produkte werden dorthin gesendet – bereit für WhatsApp, Instagram und Facebook.",
  howTo: "Die ID steht im Commerce Manager → dein Katalog → Einstellungen. Das Token gehört einem Systemnutzer (Unternehmenseinstellungen → Systemnutzer) mit der Berechtigung catalog_management und Zugriff auf den Katalog.",
  catalogId: "Katalog-ID",
  token: "Zugriffstoken",
  tokenKeep: "Leer lassen, um das aktuelle zu behalten",
  connect: "Katalog verbinden",
  disconnect: "Trennen",
  syncNow: "Jetzt synchronisieren",
  disconnectConfirm: "Katalog trennen? Produkte, die schon bei Meta sind, bleiben dort.",
  unnamed: "Katalog ohne Namen",
  neverSynced: "Noch nicht synchronisiert.",
  lastSync: "Letzte Synchronisierung: {date} · {sent} gesendet, {failed} mit Problemen",
  stillChecking: "Meta prüfte die Sendung noch; was fehlschlägt, siehst du bei der nächsten Synchronisierung.",
  autoSync: "Jede Änderung an einem Produkt wird nach wenigen Sekunden automatisch gesendet.",
  synced: "Fertig: {sent} gesendet, {removed} entfernt, {skipped} unvollständig, {failed} von Meta abgelehnt.",
  state: {
    synced: "Bei Meta",
    pending: "Nicht an Meta gesendet",
    missing: "Nicht an Meta gesendet, es fehlt: {fields}",
    refused: "Von Meta abgelehnt",
  },
  fields: {
    description: "Beschreibung",
    price: "Preis und Währung",
    url: "Link",
    image_url: "Bild",
  },
  errors: {
    token: "Meta hat das Token nicht akzeptiert: Prüfe, ob es gültig und nicht abgelaufen ist.",
    permission: "Das Token hat keine Berechtigung für diesen Katalog (catalog_management).",
    catalog_id: "Die Katalog-ID besteht nur aus Ziffern.",
    refused: "Meta hat die Anfrage abgelehnt.",
    unreachable: "Meta ist nicht erreichbar. Versuche es später noch einmal.",
    not_connected: "Verbinde zuerst einen Katalog.",
  },
};
