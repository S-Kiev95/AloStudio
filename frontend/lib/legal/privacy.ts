/**
 * The privacy policy's text, kept apart from its rendering.
 *
 * WHY THIS IS A FILE AND NOT A CMS ENTRY: Meta fetches the policy URL to
 * validate it before letting the app go live, and reads it again at App
 * Review. It has to answer an anonymous GET with real HTML, always —
 * which rules out anything that could be unpublished, expire, or sit
 * behind a login.
 *
 * ⚠️ THIS IS A STARTING TEMPLATE, NOT LEGAL ADVICE. It describes what
 * AloStudio's code actually does with data, which is the part that can
 * be stated factually. Everything about *who* operates the deployment —
 * legal name, jurisdiction, retention commitments — is a placeholder in
 * `OPERATOR` below and must be filled in and reviewed by whoever is
 * responsible for the deployment before it is published to real users.
 */

export const OPERATOR = {
  /** TODO: razón social del responsable del tratamiento. */
  legalName: "AloStudio",
  /** TODO: casilla que realmente atienda las solicitudes de datos. */
  contactEmail: "privacidad@alostudio.app",
} as const;

export const PRIVACY_LAST_UPDATED = "21 de agosto de 2026";

export type PrivacySection = {
  title: string;
  paragraphs: string[];
  bullets?: string[];
};

export const PRIVACY_SECTIONS: PrivacySection[] = [
  {
    title: "Qué es AloStudio",
    paragraphs: [
      "AloStudio es una plataforma de atención al cliente. Permite a una organización recibir y responder, desde un único lugar, los mensajes que le llegan por WhatsApp, Instagram, Facebook Messenger, correo electrónico, SMS, Telegram y un chat web.",
      "AloStudio actúa como encargado del tratamiento por cuenta de la organización que lo utiliza: es esa organización la que decide qué datos recoge de sus clientes y con qué finalidad. Si escribiste a una empresa y llegaste hasta acá, la responsable de tus datos es esa empresa, no la plataforma.",
    ],
  },
  {
    title: "Qué datos se tratan",
    paragraphs: [
      "Los datos que se almacenan son los estrictamente necesarios para sostener una conversación y darle continuidad:",
    ],
    bullets: [
      "Contenido de los mensajes intercambiados, incluidos los archivos adjuntos (imágenes, audios, documentos).",
      "Datos de contacto que el propio canal entrega: nombre público o usuario, número de teléfono, dirección de correo, identificador de la red social y foto de perfil.",
      "Metadatos de la conversación: fecha y hora, canal de origen, estado, agente asignado, etiquetas y notas internas del equipo.",
      "Datos de los agentes que usan la plataforma: nombre, correo, contraseña cifrada y registro de su actividad sobre las conversaciones.",
      "Credenciales técnicas de las cuentas conectadas (tokens de acceso de Meta y de los demás proveedores), guardadas para poder enviar y recibir en nombre de la organización.",
    ],
  },
  {
    title: "Para qué se usan",
    paragraphs: [
      "Únicamente para prestar el servicio: entregar los mensajes al equipo correcto, permitir responderlos, mantener el historial de la conversación, generar informes de atención agregados y notificar a los agentes.",
    ],
    bullets: [
      "No se venden datos personales a terceros.",
      "No se usan los mensajes para publicidad ni para perfilado comercial.",
      "No se entrenan modelos de inteligencia artificial con el contenido de las conversaciones.",
    ],
  },
  {
    title: "Datos obtenidos a través de Meta",
    paragraphs: [
      "Cuando la organización conecta una cuenta de Instagram, una Página de Facebook o un número de WhatsApp Business, AloStudio recibe de Meta los mensajes y comentarios dirigidos a esa cuenta, junto con el identificador y el nombre público de quien los envía. También recibe un token de acceso que le permite responder en nombre de esa cuenta.",
      "Ese acceso se limita a lo que la organización autorizó expresamente durante la conexión, y se puede revocar en cualquier momento desde la configuración de la cuenta de Meta correspondiente. Al revocarlo, AloStudio deja de recibir y de poder enviar mensajes por ese canal.",
      "El uso de estos datos se ajusta a las Políticas de la Plataforma de Meta.",
    ],
  },
  {
    title: "Con quién se comparten",
    paragraphs: [
      "Con los proveedores necesarios para que el servicio funcione, y sólo en la medida en que hacen falta:",
    ],
    bullets: [
      "Los propios proveedores de mensajería (Meta, Twilio, Bandwidth, Telegram y el proveedor de correo), que son quienes transportan los mensajes.",
      "El proveedor de infraestructura donde se aloja la instalación.",
      "Servicios de inteligencia artificial, únicamente si la organización activa esas funciones y sólo con el texto necesario para la función solicitada.",
      "Autoridades competentes, cuando exista una obligación legal.",
    ],
  },
  {
    title: "Cuánto tiempo se conservan",
    paragraphs: [
      "Las conversaciones y sus adjuntos se conservan mientras la organización mantenga activa su cuenta, salvo que fije un plazo menor. Los datos de los agentes se conservan mientras dure su vínculo con la organización.",
      "Al eliminarse una cuenta, se eliminan sus conversaciones, contactos, adjuntos y credenciales conectadas.",
    ],
  },
  {
    title: "Tus derechos",
    paragraphs: [
      "Podés solicitar acceder a tus datos, rectificarlos, eliminarlos, oponerte a su tratamiento o pedir una copia en formato legible. La solicitud se atiende en los plazos que fije la normativa aplicable.",
      "Como AloStudio trata los datos por cuenta de la organización con la que te comunicaste, lo más rápido suele ser dirigirse a ella. Si preferís, escribí a la dirección del pie de esta página y la derivamos.",
    ],
  },
  {
    title: "Seguridad",
    paragraphs: [
      "Las contraseñas se almacenan cifradas con bcrypt y nunca en texto plano. Las credenciales de los canales conectados no se muestran completas en ninguna pantalla. El tráfico viaja sobre HTTPS. Los webhooks entrantes pueden verificarse por firma criptográfica para rechazar eventos que no provengan del proveedor.",
      "Ningún sistema es infalible: ante un incidente que afecte datos personales, se notificará conforme a la normativa aplicable.",
    ],
  },
  {
    title: "Cambios en esta política",
    paragraphs: [
      "Si esta política cambia de forma sustancial, se actualizará la fecha del encabezado y se comunicará a las organizaciones que usan la plataforma.",
    ],
  },
];
