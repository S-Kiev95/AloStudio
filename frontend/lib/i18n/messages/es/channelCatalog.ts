export const channelCatalog = {
  telegram: {
    blurb: "Conectá un bot de Telegram con el token de BotFather.",
    tokenHelp: "El token que te dio @BotFather al crear el bot.",
    botName: "Nombre del bot",
    botNameHelp: "Opcional — el @username del bot.",
  },
  whatsapp: {
    blurb: "Número de WhatsApp Business vía la Cloud API de Meta.",
  },
  phoneNumber: "Número de teléfono",
  sms: {
    blurb: "Número de SMS a través de Bandwidth.",
  },
  twilio: {
    blurb: "Número de Twilio para SMS o WhatsApp.",
    medium: "Medio",
  },
  email: {
    blurb: "Una casilla de correo como canal de soporte.",
    address: "Dirección de email",
    imapEnabled: "Recibir correos (IMAP)",
    imapHelp: "Sin esto, lo que te escriban no entra a la bandeja.",
    imapServer: "Servidor IMAP",
    imapPort: "Puerto IMAP",
    imapUser: "Usuario IMAP",
    imapPassword: "Contraseña IMAP",
    appPasswordHelp: "Si tenés verificación en dos pasos, usá una contraseña de aplicación.",
    imapSsl: "Conexión segura IMAP (SSL)",
    smtpEnabled: "Enviar correos (SMTP)",
    smtpServer: "Servidor SMTP",
    smtpPort: "Puerto SMTP",
    smtpUser: "Usuario SMTP",
    smtpPassword: "Contraseña SMTP",
    smtpStarttls: "Conexión segura SMTP (STARTTLS)",
  },
  web: {
    blurb: "Chat embebido para tu sitio web.",
    siteUrl: "URL del sitio",
    welcomeTitle: "Título de bienvenida",
    welcomePlaceholder: "¡Hola! 👋",
    tagline: "Subtítulo",
  },
  api: {
    blurb: "Canal genérico vía API HTTP (webhook saliente opcional).",
    webhookHelp: "Opcional — adónde reenviamos los mensajes entrantes.",
  },
  facebook: {
    blurb: "Mensajes y publicaciones de tu Página de Facebook.",
    userTokenHelp: "Opcional — para refrescar el token de página al expirar.",
    instagramIdHelp: "Opcional — si la página está conectada a una cuenta de IG.",
  },
  instagram: {
    blurb: "IG Business por token. Para publicar y moderar comentarios, usá la sección Instagram del menú.",
  },
};
