import type { igCapabilities as es } from "../es/igCapabilities";
import type { Strings } from "../types";

export const igCapabilities: Strings<typeof es> = {
  publish: "Fotos, Karussells, Reels und Stories veröffentlichen",
  comments: "Kommentare lesen und beantworten, mit automatischen Regeln",
  insights: "Kennzahlen der Beiträge",
  facebook: {
    summary: "Der vollständige Weg. Der richtige, wenn du Nachrichten bearbeiten willst.",
    requirement: "Benötigt eine Facebook-Seite, die mit dem Instagram-Konto verknüpft ist.",
    dmsNote: "Nachrichten kommen mit Text und Anhängen an.",
  },
  dms: "Direktnachrichten empfangen und beantworten",
  deletePosts: "Beiträge aus AloStudio löschen",
  instagram: {
    summary: "Einfacher zu verbinden, aber Nachrichten funktionieren nicht.",
    requirement: "Braucht keine Facebook-Seite.",
    dmsNote: "Meta meldet, dass eine Nachricht angekommen ist, schickt aber den Text nicht, daher lässt sich die Konversation nicht rekonstruieren. Das ist eine Einschränkung von Meta, nicht von AloStudio.",
    deleteNote: "Meta bietet in dieser API kein Löschen an. Du musst in der Instagram-App löschen.",
  },
};
