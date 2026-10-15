/**
 * Data deletion instructions. Registered in the Meta app as the
 * "Data Deletion Instructions URL": Meta links people here when they
 * remove the app from their Facebook or Instagram settings, so it must
 * explain, without a login, how to get their data erased.
 */

import { OPERATOR, type LegalSection } from "./operator";

export const DATA_DELETION_LAST_UPDATED = "15 de octubre de 2026";

export const DATA_DELETION_SECTIONS: LegalSection[] = [
  {
    title: "Si escribiste a una empresa que usa AloStudio",
    paragraphs: [
      "Tus mensajes y datos de contacto los gestiona esa empresa a través de AloStudio. Podés pedirle directamente que los elimine, o escribirnos y derivamos la solicitud.",
      `Para pedirlo, enviá un correo a ${OPERATOR.contactEmail} con el asunto "Eliminación de datos" e indicá:`,
    ],
    bullets: [
      "El canal por el que escribiste (WhatsApp, Instagram, Messenger, correo, etc.).",
      "Tu número de teléfono, usuario o correo en ese canal, para poder ubicar tus conversaciones.",
      "El nombre de la empresa con la que te comunicaste, si lo sabés.",
    ],
  },
  {
    title: "Si conectaste tu cuenta de Facebook, Instagram, WhatsApp o Threads",
    paragraphs: ["Podés cortar el acceso y borrar los datos de dos formas:"],
    bullets: [
      "Desde AloStudio: en la configuración de la cuenta, eliminá la bandeja de entrada de ese canal. Se borran el canal y los tokens de acceso guardados y AloStudio deja de recibir y enviar por ese canal.",
      "Desde Meta: en Facebook, Configuración y privacidad > Configuración > Integraciones comerciales (o Apps y sitios web), elegí AloStudio y quitalo. En Instagram, Configuración > Permisos de apps y sitios web.",
      `Para que además se borren las conversaciones, contactos, publicaciones programadas y estadísticas asociadas, escribí a ${OPERATOR.contactEmail} desde el correo de la cuenta y pedí la eliminación completa.`,
    ],
  },
  {
    title: "Qué se elimina y en qué plazo",
    paragraphs: [
      "Se eliminan los mensajes y adjuntos, los datos de contacto, las credenciales de los canales conectados, el contenido programado y las métricas guardadas. La solicitud se confirma por correo y se completa dentro de los 30 días.",
      "Puede conservarse sólo la información que una ley obligue a guardar, y únicamente por el plazo que esa ley fije.",
    ],
  },
];
