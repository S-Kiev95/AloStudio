"""AI-assisted HTML design for email templates and signatures.

Kept strictly independent from HTTP routers so both the dashboard route
(``POST /api/v1/accounts/{account_id}/email_templates/generate``) and future
Agent / MCP tools can invoke :func:`generate_email_design` directly.

Pipeline:
  1. Optional reference screenshot (``image`` data URL) is described via
     :func:`app.core.media_ai.describe` (NVIDIA first, Groq fallback) and the
     description is woven into the design prompt.
  2. The HTML is written by the text model:
       * OpenAI (:func:`app.core.llm.chat_completion`) when the account has
         Fast enabled and an OpenAI key is configured, inside ``ai_usage``
         and respecting the monthly spend cap (:func:`ai_budget_reached`).
       * Otherwise the Free model (:func:`app.core.local_llm.chat`).
       * If no model responds, raises :class:`EmailAiError` with code
         ``ai_down`` and message ``"Servicios de AI temporalmente fuera,
         intenta mañana"``.
  3. The returned HTML is ALWAYS passed through :func:`sanitize_email_html`
     and normalized for its kind:
       * ``template``: guarantees ``{{contenido}}`` is present (injects it
         if the model omitted it).
       * ``signature``: strips any stray ``{{contenido}}``.
  4. Never persists anything — the caller opens the markup in the canvas.
"""

from __future__ import annotations

import base64
import binascii
import logging
import re
from dataclasses import dataclass
from typing import Any, Literal

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import llm, local_llm, media_ai
from app.core.config import get_settings
from app.domains.accounts.models import Account
from app.domains.email.sanitize import sanitize_email_html
from app.domains.email.template import PLACEHOLDER_CONTENT
from app.domains.help_assistant.service import fast_allowed
from app.domains.usage.ai import ai_budget_reached, ai_usage

log = logging.getLogger(__name__)

DesignKind = Literal["template", "signature"]

PURPOSE = "email_design"
PROMPT_MAX = 1500
AI_DOWN_MESSAGE = "Servicios de AI temporalmente fuera, intenta mañana"

_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "html": {"type": "string"},
        "notes": {"type": "string"},
    },
    "required": ["html", "notes"],
    "additionalProperties": False,
}

_TEMPLATE_SYSTEM = (
    "Sos diseñador de plantillas de correo electrónico compatibles con Gmail y Outlook.\n"
    "Devolvé SIEMPRE un objeto JSON válido con exactamente dos claves: "
    '{"html": "...", "notes": "..."}.\n'
    "Reglas obligatorias para el campo html:\n"
    '- Usá tablas HTML (role="presentation", cellpadding="0", cellspacing="0", border="0") '
    "y estilos 100% en línea (atributo style). Nunca uses bloques <style>, <script>, <iframe>, "
    "<form> ni manejadores on*.\n"
    "- Incluí obligatoriamente el marcador literal {{contenido}} donde va el cuerpo del mensaje.\n"
    "- Podés incluir {{logo}}, {{firma}} y {{firma_organizacion}} cuando corresponda.\n"
    "- Usá ancho máximo de 600px, buena jerarquía visual, tipografía segura (Arial, Helvetica, sans-serif) "
    "y alto contraste.\n"
    "- En notes escribí en español, en 1 o 2 oraciones breves, qué diseñaste y qué conviene personalizar."
)

_SIGNATURE_SYSTEM = (
    "Sos diseñador de firmas de correo electrónico compatibles con Gmail y Outlook.\n"
    "Devolvé SIEMPRE un objeto JSON válido con exactamente dos claves: "
    '{"html": "...", "notes": "..."}.\n'
    "Reglas obligatorias para el campo html:\n"
    '- Usá una tabla compacta (role="presentation", cellpadding="0", cellspacing="0", border="0") '
    "y estilos 100% en línea (atributo style). Nunca uses bloques <style>, <script>, <iframe>, "
    "<form> ni manejadores on*.\n"
    "- NO incluyas {{contenido}} (esto es una firma, no una plantilla completa).\n"
    "- Podés usar las variables de perfil del usuario: {{nombre}}, {{cargo}}, {{correo}}, "
    "{{telefono}} y {{foto}}.\n"
    "- Mantené un diseño compacto (ancho máximo 520px), profesional y legible.\n"
    "- En notes escribí en español, en 1 o 2 oraciones breves, qué diseñaste y qué variables incluiste."
)

_HTML_FENCE_RE = re.compile(r"```(?:html)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
_LAST_TABLE_CLOSE_RE = re.compile(r"(</table>)(?!.*</table>)", re.DOTALL | re.IGNORECASE)
_FALLBACK_CONTENT_ROW = (
    '<tr><td style="padding:20px 28px;font-size:15px;line-height:1.55;color:#1f2328">'
    f"{PLACEHOLDER_CONTENT}"
    "</td></tr>"
)


class EmailAiError(RuntimeError):
    """Domain error raised when AI design generation cannot complete."""

    def __init__(self, code: str, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(slots=True)
class GeneratedDesign:
    html: str
    notes: str
    mode: str
    seen: str | None = None


def ai_available(account: Account) -> bool:
    """True when at least one text provider (Fast or Free) is configured."""
    fast = bool(get_settings().openai_api_key) and fast_allowed(account)
    return fast or local_llm.configured()


def _parse_data_url(value: str) -> tuple[str, bytes]:
    match = re.fullmatch(r"data:([\w/+.-]+(?:;[\w=.-]+)*);base64,(.+)", value.strip(), re.S)
    if match is None:
        raise media_ai.MediaRejected("type")
    mime = match.group(1).split(";")[0].lower()
    try:
        return mime, base64.b64decode(match.group(2), validate=True)
    except (ValueError, binascii.Error) as exc:
        raise media_ai.MediaRejected("type") from exc


def _extract_html_and_notes(raw: str) -> tuple[str, str]:
    """Parse ``{"html": ..., "notes": ...}`` or gracefully unwrap raw HTML."""
    try:
        parsed = local_llm.parse_json(raw)
        html = str(parsed.get("html") or "").strip()
        notes = str(parsed.get("notes") or "").strip()
        if html:
            return html, notes
    except local_llm.LocalLlmError:
        pass

    stripped = (raw or "").strip()
    fence = _HTML_FENCE_RE.search(stripped)
    candidate = fence.group(1).strip() if fence else stripped
    if "<" in candidate and ">" in candidate:
        return candidate, ""
    raise local_llm.LocalLlmError("bad_response", "no html in model reply")


def _ensure_kind_constraints(html: str, kind: DesignKind) -> str:
    """Guarantee ``{{contenido}}`` is present on templates and absent on signatures."""
    clean = sanitize_email_html(html)
    if kind == "signature":
        clean = clean.replace(PLACEHOLDER_CONTENT, "").strip()
        if not clean:
            clean = (
                '<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
                'style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#1f2328">'
                '<tr><td style="padding:8px 0"><strong>{{nombre}}</strong><br>'
                '<span style="color:#5b6470">{{cargo}}</span><br>'
                '<span style="color:#5b6470">{{correo}}</span></td></tr></table>'
            )
        return clean

    if not clean:
        return (
            '<div style="background:#f4f5f7;padding:24px 0;font-family:Arial,Helvetica,sans-serif">'
            '<table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center" '
            'width="600" style="width:600px;max-width:100%;margin:0 auto;background:#ffffff;border-radius:8px">'
            f"{_FALLBACK_CONTENT_ROW}</table></div>"
        )
    if PLACEHOLDER_CONTENT not in clean:
        if _LAST_TABLE_CLOSE_RE.search(clean):
            clean = _LAST_TABLE_CLOSE_RE.sub(f"{_FALLBACK_CONTENT_ROW}\\1", clean, count=1)
        else:
            clean = (
                f"{clean}"
                '<div style="padding:20px 24px;font-size:15px;line-height:1.55;color:#1f2328">'
                f"{PLACEHOLDER_CONTENT}</div>"
            )
    return clean


async def _call_openai(
    messages: list[dict[str, str]],
    *,
    session: AsyncSession,
    account_id: int,
) -> str:
    with ai_usage(session, account_id, PURPOSE):
        if await ai_budget_reached():
            raise EmailAiError(
                "budget",
                "Se alcanzó el tope mensual de gasto en IA de la cuenta.",
                status_code=422,
            )
        message = await llm.chat_completion(
            messages=messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "email_design",
                    "strict": True,
                    "schema": _RESPONSE_SCHEMA,
                },
            },
        )
    return str(message.get("content") or "")


async def generate_email_design(
    session: AsyncSession,
    *,
    account: Account,
    prompt: str = "",
    kind: DesignKind = "template",
    image: str | None = None,
) -> GeneratedDesign:
    """Generate sanitized, mail-client-ready HTML for a template or signature.

    Reusable service function (independent from HTTP) so both the dashboard
    endpoint and future Agent tools share the exact same logic and safety
    guarantees.
    """
    if kind not in ("template", "signature"):
        raise EmailAiError("kind", "El tipo tiene que ser plantilla o firma.", 422)

    clean_prompt = " ".join((prompt or "").split())[:PROMPT_MAX]
    image_raw = (image or "").strip() or None
    if not clean_prompt and not image_raw:
        raise EmailAiError(
            "prompt",
            "Contanos qué querés diseñar o subí una imagen de ejemplo.",
            422,
        )

    seen: str | None = None
    if image_raw is not None:
        if not media_ai.available():
            raise EmailAiError(
                "media_off",
                "La lectura de imágenes no está configurada en esta instalación.",
                422,
            )
        try:
            mime, data = _parse_data_url(image_raw)
            media_ai.check("image", mime, data)
            seen = await media_ai.describe(data, mime)
        except media_ai.MediaRejected as exc:
            msg = (
                "La imagen supera el tamaño máximo permitido (5 MB)."
                if exc.code == "size"
                else "Formato de imagen no soportado. Usá PNG, JPG o WebP."
            )
            raise EmailAiError(f"media_{exc.code}", msg, 422) from exc
        except media_ai.MediaAiDown as exc:
            raise EmailAiError("ai_down", AI_DOWN_MESSAGE, 503) from exc

    user_parts: list[str] = []
    if clean_prompt:
        user_parts.append(f"Pedido del usuario: {clean_prompt}")
    if seen:
        user_parts.append(f"Referencia visual (imagen de ejemplo): {seen}")
    if not clean_prompt and seen:
        user_parts.append(
            "Replicá el estilo, colores y estructura descritos en la imagen de ejemplo."
        )

    system_prompt = _TEMPLATE_SYSTEM if kind == "template" else _SIGNATURE_SYSTEM
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "\n\n".join(user_parts)},
    ]

    use_fast = bool(get_settings().openai_api_key) and fast_allowed(account)
    has_free = local_llm.configured()

    raw_reply: str | None = None
    used_mode = "free"

    if use_fast and account.id is not None:
        try:
            raw_reply = await _call_openai(messages, session=session, account_id=account.id)
            used_mode = "fast"
        except EmailAiError:
            raise
        except llm.LlmError as exc:
            log.warning("email.ai_design.openai_failed error=%s", exc)
            if not has_free:
                raise EmailAiError("ai_down", AI_DOWN_MESSAGE, 503) from exc

    if raw_reply is None:
        if not has_free:
            raise EmailAiError("ai_down", AI_DOWN_MESSAGE, 503)
        try:
            raw_reply, _ = await local_llm.chat(
                messages,
                max_tokens=2400,
                temperature=0.3,
                json_schema=_RESPONSE_SCHEMA,
            )
            used_mode = "free"
        except local_llm.LocalLlmError as exc:
            log.warning("email.ai_design.free_failed code=%s", exc.code)
            raise EmailAiError("ai_down", AI_DOWN_MESSAGE, 503) from exc

    try:
        raw_html, notes = _extract_html_and_notes(raw_reply)
    except local_llm.LocalLlmError as exc:
        log.warning("email.ai_design.parse_failed reason=%s", exc)
        raise EmailAiError("ai_down", AI_DOWN_MESSAGE, 503) from exc

    final_html = _ensure_kind_constraints(raw_html, kind)
    return GeneratedDesign(
        html=final_html,
        notes=notes[:500],
        mode=used_mode,
        seen=seen,
    )


__all__ = [
    "AI_DOWN_MESSAGE",
    "PURPOSE",
    "DesignKind",
    "EmailAiError",
    "GeneratedDesign",
    "ai_available",
    "generate_email_design",
]
