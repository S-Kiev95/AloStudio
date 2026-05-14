"""Wire-shape presenter for AgentBot.

Anchors:
  reference/chatwoot/app/views/api/v1/models/_agent_bot.json.jbuilder
  reference/chatwoot/app/presenters/agent_bot_presenter.rb
"""

from __future__ import annotations

from typing import Any

from app.domains.agent_bots.models import AgentBot


def present_agent_bot(
    bot: AgentBot,
    *,
    access_token: str | None = None,
    show_secret: bool = False,
) -> dict[str, Any]:
    """Mirror ``_agent_bot.json.jbuilder``.

    ``outgoing_url`` is omitted for system bots; ``secret`` is gated
    on caller role (admin-only) AND the bot not being a system bot.
    ``access_token`` only appears when the caller created a polymorphic
    AccessToken row (not part of Phase 8 — left None until follow-up).
    """
    body: dict[str, Any] = {
        "id": bot.id,
        "name": bot.name,
        "description": bot.description,
        "thumbnail": "",
    }
    if not bot.system_bot:
        body["outgoing_url"] = bot.outgoing_url
    body["bot_type"] = "webhook"  # only enum value v4.13.0 ships
    body["bot_config"] = bot.bot_config or {}
    body["account_id"] = bot.account_id
    if access_token:
        body["access_token"] = access_token
    if show_secret and not bot.system_bot:
        body["secret"] = bot.secret
    body["system_bot"] = bot.system_bot
    return body


__all__ = ["present_agent_bot"]
