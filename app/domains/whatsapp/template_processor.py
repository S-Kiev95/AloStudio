"""Turn a campaign/message ``template_params`` blob into the ``template_info``
that :func:`app.domains.whatsapp.templates.send_template_message` expects.

Focused port of ``Whatsapp::TemplateProcessorService`` — the **text-template**
path (name + language + body ``{{1}},{{2}}`` parameters), which covers the
common campaign case. Header media, buttons and named parameters are a
follow-up (they'd extend :func:`_build_components`).

``template_params`` (stored on ``message.additional_attributes['template_params']``
by ``create_message``) is expected to look like::

    {"name": "order_update", "language": "es_AR",
     "processed_params": {"body": {"1": "Ana", "2": "#123"}}}

We validate the template exists + is APPROVED in the channel's synced
``message_templates`` before sending, so a stale/unknown name doesn't fire a
doomed request (mirrors the Rails service returning nil).
"""

from __future__ import annotations

from typing import Any


def _find_template(
    message_templates: list[dict[str, Any]] | None,
    name: str,
    language: str | None,
) -> dict[str, Any] | None:
    """Approved template matching name (+ language, case-insensitive)."""
    for tpl in message_templates or []:
        if not isinstance(tpl, dict):
            continue
        if tpl.get("name") != name:
            continue
        if str(tpl.get("status", "")).upper() != "APPROVED":
            continue
        if language is not None and (
            str(tpl.get("language", "")).lower() != language.lower()
        ):
            continue
        return tpl
    return None


def _build_components(template_params: dict[str, Any]) -> list[dict[str, Any]]:
    """Build the WhatsApp ``components`` list from the stored params.

    Text templates only for now: an ordered ``body`` parameter list. Keys
    are the ``{{1}}, {{2}}, …`` positions; we emit them in numeric order.
    """
    processed = template_params.get("processed_params")
    body = processed.get("body") if isinstance(processed, dict) else None
    if not isinstance(body, dict) or not body:
        return []

    def _order(key: str) -> tuple[int, str]:
        # Numeric positions first (1,2,3…), then any stragglers by string.
        try:
            return (int(key), "")
        except (TypeError, ValueError):
            return (10**9, str(key))

    params = [
        {"type": "text", "text": str(body[k])}
        for k in sorted(body, key=_order)
        if str(body[k]).strip()
    ]
    if not params:
        return []
    return [{"type": "body", "parameters": params}]


def process_template_params(
    template_params: dict[str, Any] | None,
    message_templates: list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    """Return ``template_info`` (``{name, lang_code, parameters}``) or ``None``.

    ``None`` means "don't send a template" — blank input, no name, or the
    named template isn't an approved variant on this channel. Callers fall
    back to a plain-text send.
    """
    if not isinstance(template_params, dict) or not template_params:
        return None
    name = template_params.get("name")
    if not name:
        return None
    language = template_params.get("language") or template_params.get(
        "lang_code"
    )
    if _find_template(message_templates, name, language) is None:
        return None
    return {
        "name": name,
        "lang_code": language,
        "parameters": _build_components(template_params),
    }


__all__ = ["process_template_params"]
