/**
 * The terms of service's text, kept apart from its rendering for the same
 * reason as the privacy policy: Meta reads the Terms URL registered on the
 * app anonymously, so it must always answer with real HTML.
 */

import { OPERATOR, type LegalSection } from "./operator";

export const TERMS_LAST_UPDATED = "15 de octubre de 2026";

export const TERMS_SECTIONS: LegalSection[] = [
  {
    title: "Aceptación",
    paragraphs: [
      `Estos términos regulan el uso de AloStudio, un servicio prestado por ${OPERATOR.legalName}. Al crear una cuenta, conectar un canal o usar la plataforma, la organización y cada persona que actúa en su nombre aceptan estos términos y la Política de privacidad.`,
    ],
  },
  {
    title: "Qué ofrece el servicio",
    paragraphs: [
      "AloStudio permite a una organización atender en un único lugar los mensajes que recibe por WhatsApp, Instagram, Facebook Messenger, correo electrónico, Telegram y otros canales; gestionar contactos, clientes, productos y citas; y programar publicaciones y consultar estadísticas en sus propias Páginas y cuentas de redes sociales.",
      "El servicio se ofrece tal como está y puede cambiar, ampliarse o reducirse con el tiempo.",
    ],
  },
  {
    title: "Cuentas y canales conectados",
    paragraphs: [
      "La organización es responsable de que las personas que invita usen credenciales propias y las mantengan en reserva, y de toda actividad realizada desde su cuenta.",
      "Al conectar una cuenta de Meta (Página de Facebook, cuenta de Instagram, número de WhatsApp Business o perfil de Threads) u otro proveedor, la organización declara que tiene autorización para administrarla y autoriza a AloStudio a enviar, recibir y publicar en su nombre dentro de los permisos otorgados. Ese acceso puede revocarse en cualquier momento desde la configuración del proveedor.",
    ],
  },
  {
    title: "Uso aceptable",
    paragraphs: ["No está permitido usar AloStudio para:"],
    bullets: [
      "Enviar spam, mensajes no solicitados o comunicaciones que incumplan las políticas de Meta, WhatsApp u otros proveedores de mensajería.",
      "Publicar o enviar contenido ilegal, engañoso, que infrinja derechos de terceros o que promueva odio o violencia.",
      "Intentar acceder sin autorización a cuentas, datos o sistemas, o interferir con el funcionamiento del servicio.",
      "Revender el servicio o usarlo para fines distintos a la atención y comunicación de la propia organización.",
    ],
  },
  {
    title: "Datos y privacidad",
    paragraphs: [
      "La organización conserva la titularidad de sus datos y de los de sus clientes, y es la responsable de contar con una base legal para tratarlos. AloStudio los trata por cuenta de la organización según se describe en la Política de privacidad.",
    ],
  },
  {
    title: "Servicios de terceros",
    paragraphs: [
      "El servicio depende de plataformas de terceros (Meta, proveedores de mensajería, correo e infraestructura). Su disponibilidad, sus límites y sus cambios de política quedan fuera del control de AloStudio, y el uso de esos canales queda sujeto también a sus propios términos.",
    ],
  },
  {
    title: "Suspensión y baja",
    paragraphs: [
      "La organización puede dejar de usar el servicio y solicitar la eliminación de su cuenta en cualquier momento. AloStudio puede suspender una cuenta que incumpla estos términos o las políticas de los proveedores conectados, o cuando lo exija una autoridad competente.",
    ],
  },
  {
    title: "Responsabilidad",
    paragraphs: [
      "En la máxima medida que permita la ley, AloStudio no responde por daños indirectos, lucro cesante ni pérdida de datos derivados del uso o la imposibilidad de uso del servicio, ni por fallas de los proveedores de terceros.",
    ],
  },
  {
    title: "Ley aplicable",
    paragraphs: [
      `Estos términos se rigen por las leyes de la República Oriental del ${OPERATOR.country}. Cualquier controversia se someterá a los tribunales competentes de ese país.`,
    ],
  },
  {
    title: "Cambios en estos términos",
    paragraphs: [
      "Si estos términos cambian de forma sustancial, se actualizará la fecha del encabezado y se avisará a las organizaciones que usan la plataforma. Seguir usando el servicio después del aviso implica aceptar la nueva versión.",
    ],
  },
];
