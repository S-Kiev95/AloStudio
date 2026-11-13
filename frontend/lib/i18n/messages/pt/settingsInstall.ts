import type { settingsInstall as es } from "../es/settingsInstall";
import type { Strings } from "../types";

export const settingsInstall: Strings<typeof es> = {
  configuredCount: "{done}/{total} configurados",
  netConfigured: "configurada",
  netNotConfigured: "não configurada",
  operatorOnly: "Só o operador da instalação pode ver esta tela. Peça acesso a quem a implantou.",
  loadFailed: "Não foi possível carregar a configuração.",
  intro: "Ajustes que valem para todo o AloStudio, não para uma conta. Você pode deixá-los vazios e preenchê-los quando tiver as credenciais — o app funciona sem eles, e cada função avisa o que está faltando.",
  network: "Rede",
  clearFailed: "Não foi possível apagar.",
  notConfigured: "Não configurado",
  configured: "Configurado",
  savedHere: "salvo por aqui",
  resetToServer: "voltar ao valor do servidor",
  fromEnv: "vem do arquivo do servidor (.env)",
  groups: {
    meta: "Meta (Facebook e Instagram)",
    mail: "Email de saída",
    publishing: "Redes para publicar",
    access: "Acesso",
    webhooks: "Webhooks",
    brand: "Marca",
    ai: "Inteligência artificial",
  },
  items: {
    META_APP_ID: {
      title: "App ID do Facebook",
      description: "Identifica o AloStudio perante a Meta no fluxo do Facebook Login. É um só para toda a instalação, não um por cliente.",
    },
    META_APP_SECRET: {
      title: "App Secret do Facebook",
      description: "Chave secreta do mesmo app. É usada na troca de tokens.",
    },
    META_INSTAGRAM_APP_ID: {
      title: "App ID do Instagram",
      description: "Para o fluxo do Instagram Login, que não precisa de Página do Facebook. É um app diferente do do Facebook.",
    },
    META_INSTAGRAM_APP_SECRET: {
      title: "App Secret do Instagram",
      description: "Chave secreta do app do Instagram.",
    },
    META_OAUTH_REDIRECT_URI: {
      title: "URL de retorno do OAuth",
      description: "Para onde o navegador volta depois de autorizar. Tem que coincidir *exatamente* com a que você cadastrou no painel da Meta, incluindo o https e a barra final.",
    },
    SMTP_HOST: {
      title: "Servidor SMTP",
      description: "Por onde saem os emails do AloStudio (recuperar senha, confirmações, convites, avisos). Com Gmail: smtp.gmail.com.",
    },
    SMTP_PORT: {
      title: "Porta SMTP",
      description: "Com Gmail: 465 (com TLS ativado).",
    },
    SMTP_TLS: {
      title: "Conexão criptografada (TLS)",
      description: "Ativado para a porta 465 (Gmail).",
    },
    SMTP_USER: {
      title: "Usuário SMTP",
      description: "Com Gmail: o endereço completo da conta que envia.",
    },
    SMTP_PASSWORD: {
      title: "Senha SMTP",
      description: "Com Gmail: uma senha de app de 16 letras (Conta do Google → Segurança → Senhas de app; precisa da verificação em duas etapas). Não a da sua conta.",
    },
    MAIL_FROM: {
      title: "Remetente",
      description: "Quem aparece como remetente, por exemplo \"AloStudio <seuemail@gmail.com>\". Com Gmail tem que ser a mesma conta.",
    },
    PUBLISHING_OAUTH_REDIRECT_URI: {
      title: "URL de retorno ao conectar redes",
      description: "Uma única URL para todas as redes conectadas pelo calendário (Threads, LinkedIn, TikTok, X e as que forem adicionadas): para onde o navegador volta depois de autorizar. É https://<seu domínio>/api/v1/publishing/oauth/callback e é cadastrada igual no app de desenvolvedor de cada rede.",
    },
    THREADS_APP_ID: {
      title: "App ID do Threads",
      description: "O \"Threads App ID\" do app da Meta (Configurações básicas), diferente do App ID do Facebook e do Instagram.",
    },
    THREADS_APP_SECRET: {
      title: "App Secret do Threads",
      description: "A chave secreta do Threads do mesmo app.",
    },
    LINKEDIN_CLIENT_ID: {
      title: "Client ID do LinkedIn",
      description: "Do app em linkedin.com/developers, aba Auth.",
    },
    LINKEDIN_CLIENT_SECRET: {
      title: "Client Secret do LinkedIn",
      description: "O Primary Client Secret da mesma aba Auth.",
    },
    TIKTOK_CLIENT_KEY: {
      title: "Client key do TikTok",
      description: "Do app em developers.tiktok.com, seção App details → Credentials.",
    },
    TIKTOK_CLIENT_SECRET: {
      title: "Client secret do TikTok",
      description: "O Client secret da mesma seção.",
    },
    TIKTOK_VERIFICATION_FILE: {
      title: "Arquivo de verificação do TikTok: nome",
      description: "Ao verificar o prefixo de URL https://<domínio>/ no app do TikTok (URL properties), o TikTok dá um arquivo para baixar. Cole aqui o nome exato dele, por exemplo tiktokAbC123.txt. Produção e cada sandbox dão um diferente: separe-os com vírgulas.",
    },
    TIKTOK_VERIFICATION_CONTENT: {
      title: "Arquivo de verificação do TikTok: conteúdo",
      description: "O texto que está dentro desse arquivo (abra com o Bloco de notas). Se houver vários arquivos, cole o texto de cada um separado por vírgulas.",
    },
    X_CLIENT_ID: {
      title: "Client ID do X",
      description: "Do app em console.x.com, seção Keys and tokens → OAuth 2.0. O app tem que ser do tipo Web App, com permissão de leitura e escrita.",
    },
    X_CLIENT_SECRET: {
      title: "Client Secret do X",
      description: "O OAuth 2.0 Client Secret da mesma seção.",
    },
    ENABLE_ACCOUNT_SIGNUP: {
      title: "Cadastro aberto de contas",
      description: "Deixa qualquer pessoa que chegar à URL criar uma conta e entrar como administrador, sem confirmar o email. Desativado, só o operador cria contas. Ative apenas se a instalação for de autoatendimento.",
    },
    GOOGLE_CLIENT_ID: {
      title: "Entrar com Google: Client ID",
      description: "Do ID do cliente OAuth (aplicativo da Web) em console.cloud.google.com. Com este dado e o secret, a tela de login mostra «Entrar com Google». Só entram usuários já convidados. URL de redirecionamento autorizada: https://<domínio>/auth/google/callback.",
    },
    GOOGLE_CLIENT_SECRET: {
      title: "Entrar com Google: Client secret",
      description: "O secret do mesmo ID do cliente OAuth.",
    },
    GOOGLE_ALLOWED_DOMAIN: {
      title: "Entrar com Google: domínio permitido",
      description: "Opcional. Um domínio do Google Workspace (por exemplo, minhaescola.edu.br): só são aceitas contas desse domínio. Vazio, qualquer conta do Google com o email de um usuário convidado.",
    },
    META_VERIFY_WEBHOOK_SIGNATURE: {
      title: "Verificar a assinatura dos webhooks",
      description: "Rejeita os webhooks da Meta cuja assinatura não for válida. Precisa do App Secret cadastrado. Deixe ativado em produção.",
    },
    FB_VERIFY_TOKEN: {
      title: "Token de verificação do Messenger",
      description: "O texto que você colocou no painel da Meta ao cadastrar o webhook do Messenger. A Meta o repete para comprovar que a URL é sua.",
    },
    IG_VERIFY_TOKEN: {
      title: "Token de verificação do Instagram",
      description: "O mesmo, para o webhook do Instagram.",
    },
    APP_BASE_URL: {
      title: "URL pública do painel",
      description: "O endereço usado para montar os links dos emails, dos anexos e do retorno do OAuth.",
    },
    OPENAI_API_KEY: {
      title: "Chave da OpenAI",
      description: "Usada pelo agente com chat e pela busca do Help Center. É criada em platform.openai.com e cobra por uso nessa conta.",
    },
    OPENAI_AGENT_MODEL: {
      title: "Modelo do agente",
      description: "O modelo da OpenAI que o agente com chat usa, por exemplo gpt-5.4-mini (rápido e barato) ou gpt-5.5 (mais capaz).",
    },
  },
};
