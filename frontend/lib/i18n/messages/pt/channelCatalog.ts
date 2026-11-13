import type { channelCatalog as es } from "../es/channelCatalog";
import type { Strings } from "../types";

export const channelCatalog: Strings<typeof es> = {
  telegram: {
    blurb: "Conecte um bot do Telegram com o token do BotFather.",
    tokenHelp: "O token que o @BotFather te deu ao criar o bot.",
    botName: "Nome do bot",
    botNameHelp: "Opcional — o @username do bot.",
  },
  whatsapp: {
    blurb: "Número do WhatsApp Business pela Cloud API da Meta.",
  },
  phoneNumber: "Número de telefone",
  sms: {
    blurb: "Número de SMS pela Bandwidth.",
  },
  twilio: {
    blurb: "Número da Twilio para SMS ou WhatsApp.",
    medium: "Meio",
  },
  email: {
    blurb: "Uma caixa de email como canal de suporte.",
    address: "Endereço de email",
    imapEnabled: "Receber emails (IMAP)",
    imapHelp: "Sem isso, o que te escreverem não entra na caixa de entrada.",
    imapServer: "Servidor IMAP",
    imapPort: "Porta IMAP",
    imapUser: "Usuário IMAP",
    imapPassword: "Senha IMAP",
    appPasswordHelp: "Se você usa verificação em duas etapas, use uma senha de app.",
    imapSsl: "Conexão segura IMAP (SSL)",
    smtpEnabled: "Enviar emails (SMTP)",
    smtpServer: "Servidor SMTP",
    smtpPort: "Porta SMTP",
    smtpUser: "Usuário SMTP",
    smtpPassword: "Senha SMTP",
    smtpStarttls: "Conexão segura SMTP (STARTTLS)",
  },
  web: {
    blurb: "Chat incorporado para o seu site.",
    siteUrl: "URL do site",
    welcomeTitle: "Título de boas-vindas",
    welcomePlaceholder: "Olá! 👋",
    tagline: "Subtítulo",
  },
  api: {
    blurb: "Canal genérico via API HTTP (webhook de saída opcional).",
    webhookHelp: "Opcional — para onde reenviamos as mensagens recebidas.",
  },
  facebook: {
    blurb: "Mensagens e publicações da sua Página do Facebook.",
    userTokenHelp: "Opcional — para renovar o token da página quando expirar.",
    instagramIdHelp: "Opcional — se a página estiver conectada a uma conta do IG.",
  },
  instagram: {
    blurb: "IG Business por token. Para publicar e moderar comentários, use a seção Instagram do menu.",
  },
};
