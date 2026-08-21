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


META_GROUP = "Meta (Facebook e Instagram)"
WEBHOOK_GROUP = "Webhooks"
BRAND_GROUP = "Marca"

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
    # --- Webhooks ------------------------------------------------------
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
)

SPECS_BY_NAME: dict[str, ConfigSpec] = {s.name: s for s in CONFIG_SPECS}


def spec_for(name: str) -> ConfigSpec | None:
    return SPECS_BY_NAME.get(name)


__all__ = ["CONFIG_SPECS", "SPECS_BY_NAME", "ConfigSpec", "spec_for"]
