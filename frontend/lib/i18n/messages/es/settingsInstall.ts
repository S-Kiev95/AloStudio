export const settingsInstall = {
  configuredCount: "{done}/{total} configurados",
  netConfigured: "configurada",
  netNotConfigured: "sin configurar",
  operatorOnly: "Sólo el operador de la instalación puede ver esta pantalla. Pedile acceso a quien la desplegó.",
  loadFailed: "No se pudo cargar la configuración.",
  intro: "Ajustes que valen para todo AloStudio, no para una cuenta. Podés dejarlos vacíos y completarlos cuando tengas las credenciales — la app funciona sin ellos, y cada función te avisa qué le falta.",
  network: "Red",
  clearFailed: "No se pudo borrar.",
  notConfigured: "Sin configurar",
  configured: "Configurado",
  savedHere: "guardado desde acá",
  resetToServer: "volver al valor del servidor",
  fromEnv: "viene del archivo del servidor (.env)",
  groups: {
    meta: "Meta (Facebook e Instagram)",
    mail: "Correo saliente",
    publishing: "Redes para publicar",
    access: "Acceso",
    webhooks: "Webhooks",
    brand: "Marca",
    ai: "Inteligencia artificial",
  },
  items: {
    META_APP_ID: {
      title: "App ID de Facebook",
      description: "Identifica a AloStudio ante Meta en el flujo de Facebook Login. Es uno solo para toda la instalación, no uno por cliente.",
    },
    META_APP_SECRET: {
      title: "App Secret de Facebook",
      description: "Clave secreta de la misma app. Se usa para el intercambio de tokens.",
    },
    META_INSTAGRAM_APP_ID: {
      title: "App ID de Instagram",
      description: "Para el flujo de Instagram Login, que no necesita Página de Facebook. Es una app distinta de la de Facebook.",
    },
    META_INSTAGRAM_APP_SECRET: {
      title: "App Secret de Instagram",
      description: "Clave secreta de la app de Instagram.",
    },
    META_OAUTH_REDIRECT_URI: {
      title: "URL de retorno del OAuth",
      description: "Adónde vuelve el navegador después de autorizar. Tiene que coincidir *exactamente* con la que cargaste en el panel de Meta, incluido el https y la barra final.",
    },
    SMTP_HOST: {
      title: "Servidor SMTP",
      description: "Por dónde salen los emails de AloStudio (recuperar contraseña, confirmaciones, invitaciones, avisos). Con Gmail: smtp.gmail.com.",
    },
    SMTP_PORT: {
      title: "Puerto SMTP",
      description: "Con Gmail: 465 (con TLS activado).",
    },
    SMTP_TLS: {
      title: "Conexión cifrada (TLS)",
      description: "Activado para el puerto 465 (Gmail).",
    },
    SMTP_USER: {
      title: "Usuario SMTP",
      description: "Con Gmail: la dirección completa de la cuenta que envía.",
    },
    SMTP_PASSWORD: {
      title: "Contraseña SMTP",
      description: "Con Gmail: una contraseña de aplicación de 16 letras (Cuenta de Google → Seguridad → Contraseñas de aplicaciones; necesita la verificación en dos pasos). No la de tu cuenta.",
    },
    MAIL_FROM: {
      title: "Remitente",
      description: "Quién figura como remitente, por ejemplo \"AloStudio <tucorreo@gmail.com>\". Con Gmail tiene que ser la misma cuenta.",
    },
    PUBLISHING_OAUTH_REDIRECT_URI: {
      title: "URL de retorno al conectar redes",
      description: "Una sola URL para todas las redes que se conectan desde el calendario (Threads, LinkedIn, TikTok, X y las que se sumen): adónde vuelve el navegador después de autorizar. Es https://<tu dominio>/api/v1/publishing/oauth/callback y se carga igual en la app de desarrollador de cada red.",
    },
    THREADS_APP_ID: {
      title: "App ID de Threads",
      description: "El \"Threads App ID\" de la app de Meta (Configuración básica), distinto del App ID de Facebook y del de Instagram.",
    },
    THREADS_APP_SECRET: {
      title: "App Secret de Threads",
      description: "La clave secreta de Threads de la misma app.",
    },
    LINKEDIN_CLIENT_ID: {
      title: "Client ID de LinkedIn",
      description: "De la app en linkedin.com/developers, pestaña Auth.",
    },
    LINKEDIN_CLIENT_SECRET: {
      title: "Client Secret de LinkedIn",
      description: "El Primary Client Secret de la misma pestaña Auth.",
    },
    TIKTOK_CLIENT_KEY: {
      title: "Client key de TikTok",
      description: "De la app en developers.tiktok.com, sección App details → Credentials.",
    },
    TIKTOK_CLIENT_SECRET: {
      title: "Client secret de TikTok",
      description: "El Client secret de la misma sección.",
    },
    TIKTOK_VERIFICATION_FILE: {
      title: "Archivo de verificación de TikTok: nombre",
      description: "Al verificar el prefijo de URL https://<dominio>/ en la app de TikTok (URL properties), TikTok da un archivo para descargar. Pegá acá su nombre tal cual, por ejemplo tiktokAbC123.txt. Producción y cada sandbox dan uno distinto: separalos con comas.",
    },
    TIKTOK_VERIFICATION_CONTENT: {
      title: "Archivo de verificación de TikTok: contenido",
      description: "El texto que tiene adentro ese archivo (abrilo con el Bloc de notas). Si hay varios archivos, pegá el texto de cada uno separado por comas.",
    },
    X_CLIENT_ID: {
      title: "Client ID de X",
      description: "De la app en console.x.com, sección Keys and tokens → OAuth 2.0. La app tiene que ser de tipo Web App, con permiso de lectura y escritura.",
    },
    X_CLIENT_SECRET: {
      title: "Client Secret de X",
      description: "El OAuth 2.0 Client Secret de la misma sección.",
    },
    ENABLE_ACCOUNT_SIGNUP: {
      title: "Registro abierto de cuentas",
      description: "Deja que cualquiera que llegue a la URL se cree una cuenta y entre como administrador, sin confirmar el correo. Apagado, sólo el operador da de alta cuentas. Activalo únicamente si la instalación es de autoservicio.",
    },
    GOOGLE_CLIENT_ID: {
      title: "Ingreso con Google: Client ID",
      description: "Del ID de cliente OAuth (aplicación web) en console.cloud.google.com. Con este dato y el secret, la pantalla de ingreso muestra «Entrar con Google». Solo entran usuarios ya invitados. URL de redirección autorizada: https://<dominio>/auth/google/callback.",
    },
    GOOGLE_CLIENT_SECRET: {
      title: "Ingreso con Google: Client secret",
      description: "El secret del mismo ID de cliente OAuth.",
    },
    GOOGLE_ALLOWED_DOMAIN: {
      title: "Ingreso con Google: dominio permitido",
      description: "Opcional. Un dominio de Google Workspace (por ejemplo, miescuela.edu.uy): solo se aceptan cuentas de ese dominio. Vacío, cualquier cuenta de Google con el correo de un usuario invitado.",
    },
    META_VERIFY_WEBHOOK_SIGNATURE: {
      title: "Verificar la firma de los webhooks",
      description: "Rechaza los webhooks de Meta cuya firma no valide. Necesita el App Secret cargado. Dejalo activado en producción.",
    },
    FB_VERIFY_TOKEN: {
      title: "Token de verificación de Messenger",
      description: "El texto que pusiste en el panel de Meta al dar de alta el webhook de Messenger. Meta lo repite para comprobar que la URL es tuya.",
    },
    IG_VERIFY_TOKEN: {
      title: "Token de verificación de Instagram",
      description: "Lo mismo, para el webhook de Instagram.",
    },
    APP_BASE_URL: {
      title: "URL pública del panel",
      description: "Con qué dirección se arman los enlaces de los correos, los adjuntos y la vuelta del OAuth.",
    },
    OPENAI_API_KEY: {
      title: "Clave de OpenAI",
      description: "La usan el agente con chat y la búsqueda del Help Center. Se crea en platform.openai.com y cobra por uso en esa cuenta.",
    },
    OPENAI_AGENT_MODEL: {
      title: "Modelo del agente",
      description: "El modelo de OpenAI que usa el agente con chat, por ejemplo gpt-5.4-mini (rápido y barato) o gpt-5.5 (más capaz).",
    },
  },
};
