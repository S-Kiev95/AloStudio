"""What the dashboard is allowed to configure, and how to show it.

A declaration rather than a free-for-all: an admin screen that can write
any key into the settings overlay is an arbitrary-config-injection hole,
and a screen that lists every field of ``Settings`` would offer to edit
the database URL.

Each entry names a real attribute of :class:`app.core.config.Settings`.
The environment stays the default; a row in ``installation_configs``
overrides it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class ConfigSpec:
    """One editable installation setting."""

    name: str
    """Uppercase config name — also the env var, and the row's ``name``."""

    setting: str
    """The matching ``Settings`` attribute (lowercase)."""

    title: str
    description: str
    group: str
    kind: Literal["text", "password", "boolean"] = "text"
    secret: bool = False
    """Never echoed back in full — the API returns a masked preview."""
    network: str | None = None
    """The publishing network it belongs to (``tiktok``…): the dashboard
    shows one network's settings at a time."""


META_GROUP = "Meta (Facebook e Instagram)"
WEBHOOK_GROUP = "Webhooks"
BRAND_GROUP = "Marca"
ACCESS_GROUP = "Acceso"
PUBLISHING_GROUP = "Redes para publicar"
MAIL_GROUP = "Correo saliente"
AI_GROUP = "Inteligencia artificial"

CONFIG_SPECS: tuple[ConfigSpec, ...] = (
    # --- Facebook Login (Messenger + the full Instagram API) -----------
    ConfigSpec(
        name="META_APP_ID",
        setting="meta_app_id",
        title="App ID de Facebook",
        description=(
            "Identifica a AloStudio ante Meta en el flujo de Facebook "
            "Login. Es uno solo para toda la instalación, no uno por "
            "cliente."
        ),
        group=META_GROUP,
    ),
    ConfigSpec(
        name="META_APP_SECRET",
        setting="meta_app_secret",
        title="App Secret de Facebook",
        description="Clave secreta de la misma app. Se usa para el intercambio de tokens.",
        group=META_GROUP,
        kind="password",
        secret=True,
    ),
    # --- Instagram Login (no Facebook Page) ----------------------------
    ConfigSpec(
        name="META_INSTAGRAM_APP_ID",
        setting="meta_instagram_app_id",
        title="App ID de Instagram",
        description=(
            "Para el flujo de Instagram Login, que no necesita Página de "
            "Facebook. Es una app distinta de la de Facebook."
        ),
        group=META_GROUP,
    ),
    ConfigSpec(
        name="META_INSTAGRAM_APP_SECRET",
        setting="meta_instagram_app_secret",
        title="App Secret de Instagram",
        description="Clave secreta de la app de Instagram.",
        group=META_GROUP,
        kind="password",
        secret=True,
    ),
    ConfigSpec(
        name="META_OAUTH_REDIRECT_URI",
        setting="meta_oauth_redirect_uri",
        title="URL de retorno del OAuth",
        description=(
            "Adónde vuelve el navegador después de autorizar. Tiene que "
            "coincidir *exactamente* con la que cargaste en el panel de "
            "Meta, incluido el https y la barra final."
        ),
        group=META_GROUP,
    ),
    # --- Outgoing mail (resets, confirmations, invitations) ------------
    ConfigSpec(
        name="SMTP_HOST",
        setting="smtp_host",
        title="Servidor SMTP",
        description=(
            "Por dónde salen los emails de AloStudio (recuperar contraseña, "
            "confirmaciones, invitaciones, avisos). Con Gmail: smtp.gmail.com."
        ),
        group=MAIL_GROUP,
    ),
    ConfigSpec(
        name="SMTP_PORT",
        setting="smtp_port",
        title="Puerto SMTP",
        description="Con Gmail: 465 (con TLS activado).",
        group=MAIL_GROUP,
    ),
    ConfigSpec(
        name="SMTP_TLS",
        setting="smtp_tls",
        title="Conexión cifrada (TLS)",
        description="Activado para el puerto 465 (Gmail).",
        group=MAIL_GROUP,
        kind="boolean",
    ),
    ConfigSpec(
        name="SMTP_USER",
        setting="smtp_user",
        title="Usuario SMTP",
        description="Con Gmail: la dirección completa de la cuenta que envía.",
        group=MAIL_GROUP,
    ),
    ConfigSpec(
        name="SMTP_PASSWORD",
        setting="smtp_password",
        title="Contraseña SMTP",
        description=(
            "Con Gmail: una contraseña de aplicación de 16 letras "
            "(Cuenta de Google → Seguridad → Contraseñas de aplicaciones; "
            "necesita la verificación en dos pasos). No la de tu cuenta."
        ),
        group=MAIL_GROUP,
        kind="password",
        secret=True,
    ),
    ConfigSpec(
        name="MAIL_FROM",
        setting="mail_from",
        title="Remitente",
        description=(
            'Quién figura como remitente, por ejemplo "AloStudio '
            '<tucorreo@gmail.com>". Con Gmail tiene que ser la misma cuenta.'
        ),
        group=MAIL_GROUP,
    ),
    # --- Publishing networks -------------------------------------------
    ConfigSpec(
        name="PUBLISHING_OAUTH_REDIRECT_URI",
        setting="publishing_oauth_redirect_uri",
        title="URL de retorno al conectar redes",
        description=(
            "Una sola URL para todas las redes que se conectan desde el "
            "calendario (Threads, LinkedIn, TikTok, X y las que se sumen): adónde vuelve "
            "el navegador después de autorizar. Es "
            "https://<tu dominio>/api/v1/publishing/oauth/callback y se carga "
            "igual en la app de desarrollador de cada red."
        ),
        group=PUBLISHING_GROUP,
    ),
    ConfigSpec(
        name="THREADS_APP_ID",
        setting="threads_app_id",
        title="App ID de Threads",
        description=(
            "El \"Threads App ID\" de la app de Meta (Configuración básica), "
            "distinto del App ID de Facebook y del de Instagram."
        ),
        group=PUBLISHING_GROUP,
        network="threads",
    ),
    ConfigSpec(
        name="THREADS_APP_SECRET",
        setting="threads_app_secret",
        title="App Secret de Threads",
        description="La clave secreta de Threads de la misma app.",
        group=PUBLISHING_GROUP,
        network="threads",
        kind="password",
        secret=True,
    ),
    ConfigSpec(
        name="LINKEDIN_CLIENT_ID",
        setting="linkedin_client_id",
        title="Client ID de LinkedIn",
        description="De la app en linkedin.com/developers, pestaña Auth.",
        group=PUBLISHING_GROUP,
        network="linkedin",
    ),
    ConfigSpec(
        name="LINKEDIN_CLIENT_SECRET",
        setting="linkedin_client_secret",
        title="Client Secret de LinkedIn",
        description="El Primary Client Secret de la misma pestaña Auth.",
        group=PUBLISHING_GROUP,
        network="linkedin",
        kind="password",
        secret=True,
    ),
    ConfigSpec(
        name="TIKTOK_CLIENT_KEY",
        setting="tiktok_client_key",
        title="Client key de TikTok",
        description="De la app en developers.tiktok.com, sección App details → Credentials.",
        group=PUBLISHING_GROUP,
        network="tiktok",
    ),
    ConfigSpec(
        name="TIKTOK_CLIENT_SECRET",
        setting="tiktok_client_secret",
        title="Client secret de TikTok",
        description="El Client secret de la misma sección.",
        group=PUBLISHING_GROUP,
        network="tiktok",
        kind="password",
        secret=True,
    ),
    ConfigSpec(
        name="TIKTOK_VERIFICATION_FILE",
        setting="tiktok_verification_file",
        title="Archivo de verificación de TikTok: nombre",
        description=(
            "Al verificar el prefijo de URL https://<dominio>/ en la app de TikTok "
            "(URL properties), TikTok da un archivo para descargar. Pegá acá su nombre "
            "tal cual, por ejemplo tiktokAbC123.txt. Producción y cada sandbox dan uno "
            "distinto: separalos con comas."
        ),
        group=PUBLISHING_GROUP,
        network="tiktok",
    ),
    ConfigSpec(
        name="TIKTOK_VERIFICATION_CONTENT",
        setting="tiktok_verification_content",
        title="Archivo de verificación de TikTok: contenido",
        description=(
            "El texto que tiene adentro ese archivo (abrilo con el Bloc de notas). Si hay "
            "varios archivos, pegá el texto de cada uno separado por comas."
        ),
        group=PUBLISHING_GROUP,
        network="tiktok",
    ),
    ConfigSpec(
        name="X_CLIENT_ID",
        setting="x_client_id",
        title="Client ID de X",
        description=(
            "De la app en console.x.com, sección Keys and tokens → OAuth 2.0. "
            "La app tiene que ser de tipo Web App, con permiso de lectura y escritura."
        ),
        group=PUBLISHING_GROUP,
        network="x",
    ),
    ConfigSpec(
        name="X_CLIENT_SECRET",
        setting="x_client_secret",
        title="Client Secret de X",
        description="El OAuth 2.0 Client Secret de la misma sección.",
        group=PUBLISHING_GROUP,
        network="x",
        kind="password",
        secret=True,
    ),
    # --- Webhooks ------------------------------------------------------
    ConfigSpec(
        name="ENABLE_ACCOUNT_SIGNUP",
        setting="enable_account_signup",
        title="Registro abierto de cuentas",
        description=(
            "Deja que cualquiera que llegue a la URL se cree una cuenta y "
            "entre como administrador, sin confirmar el correo. Apagado, "
            "sólo el operador da de alta cuentas. Activalo únicamente si la "
            "instalación es de autoservicio."
        ),
        group=ACCESS_GROUP,
        kind="boolean",
    ),
    ConfigSpec(
        name="GOOGLE_CLIENT_ID",
        setting="google_client_id",
        title="Ingreso con Google: Client ID",
        description=(
            "Del ID de cliente OAuth (aplicación web) en console.cloud.google.com. "
            "Con este dato y el secret, la pantalla de ingreso muestra «Entrar con "
            "Google». Solo entran usuarios ya invitados. URL de redirección "
            "autorizada: https://<dominio>/auth/google/callback."
        ),
        group=ACCESS_GROUP,
    ),
    ConfigSpec(
        name="GOOGLE_CLIENT_SECRET",
        setting="google_client_secret",
        title="Ingreso con Google: Client secret",
        description="El secret del mismo ID de cliente OAuth.",
        group=ACCESS_GROUP,
        kind="password",
        secret=True,
    ),
    ConfigSpec(
        name="GOOGLE_ALLOWED_DOMAIN",
        setting="google_allowed_domain",
        title="Ingreso con Google: dominio permitido",
        description=(
            "Opcional. Un dominio de Google Workspace (por ejemplo, miescuela.edu.uy): "
            "solo se aceptan cuentas de ese dominio. Vacío, cualquier cuenta de Google "
            "con el correo de un usuario invitado."
        ),
        group=ACCESS_GROUP,
    ),
    ConfigSpec(
        name="META_VERIFY_WEBHOOK_SIGNATURE",
        setting="meta_verify_webhook_signature",
        title="Verificar la firma de los webhooks",
        description=(
            "Rechaza los webhooks de Meta cuya firma no valide. Necesita "
            "el App Secret cargado. Dejalo activado en producción."
        ),
        group=WEBHOOK_GROUP,
        kind="boolean",
    ),
    ConfigSpec(
        name="FB_VERIFY_TOKEN",
        setting="fb_verify_token",
        title="Token de verificación de Messenger",
        description=(
            "El texto que pusiste en el panel de Meta al dar de alta el "
            "webhook de Messenger. Meta lo repite para comprobar que la "
            "URL es tuya."
        ),
        group=WEBHOOK_GROUP,
        kind="password",
        secret=True,
    ),
    ConfigSpec(
        name="IG_VERIFY_TOKEN",
        setting="ig_verify_token",
        title="Token de verificación de Instagram",
        description="Lo mismo, para el webhook de Instagram.",
        group=WEBHOOK_GROUP,
        kind="password",
        secret=True,
    ),
    # --- Branding ------------------------------------------------------
    ConfigSpec(
        name="APP_BASE_URL",
        setting="app_base_url",
        title="URL pública del panel",
        description=(
            "Con qué dirección se arman los enlaces de los correos, los "
            "adjuntos y la vuelta del OAuth."
        ),
        group=BRAND_GROUP,
    ),
    # --- AI --------------------------------------------------------------
    ConfigSpec(
        name="OPENAI_API_KEY",
        setting="openai_api_key",
        title="Clave de OpenAI",
        description=(
            "La usan el agente con chat y la búsqueda del Help Center. Se "
            "crea en platform.openai.com y cobra por uso en esa cuenta."
        ),
        group=AI_GROUP,
        kind="password",
        secret=True,
    ),
    ConfigSpec(
        name="OPENAI_AGENT_MODEL",
        setting="openai_agent_model",
        title="Modelo del agente",
        description=(
            "El modelo de OpenAI que usa el agente con chat, por ejemplo "
            "gpt-5.4-mini (rápido y barato) o gpt-5.5 (más capaz)."
        ),
        group=AI_GROUP,
    ),
)

SPECS_BY_NAME: dict[str, ConfigSpec] = {s.name: s for s in CONFIG_SPECS}


def spec_for(name: str) -> ConfigSpec | None:
    return SPECS_BY_NAME.get(name)


__all__ = ["CONFIG_SPECS", "SPECS_BY_NAME", "ConfigSpec", "spec_for"]
