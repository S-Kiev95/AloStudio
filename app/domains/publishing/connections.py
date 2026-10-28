"""Connecting channels of networks that don't publish through an inbox.

The owner asks to connect a network, their browser goes to that network to
authorize an account and comes back to one callback for every network
(``publishing_oauth_redirect_uri``); the signed ``state`` says which account
and network it was. The account becomes a channel — or refreshes the one it
already is, matched by the network's account id. Every network step goes
through the adapter, so nothing here names a network.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.errors import ChatwootHTTPException
from app.core.oauth_state import sign_oauth_state
from app.domains.publishing.adapters import (
    ChannelConnectionError,
    PublishingAdapter,
    adapter_for_network,
    connectable_adapters,
    mark_reconnect,
)
from app.domains.publishing.models import (
    CHANNEL_STATUS_ACTIVE,
    PublishingChannel,
)

log = logging.getLogger(__name__)

# Renew tokens this long before they expire (the daily job runs well inside).
REFRESH_BEFORE = timedelta(days=10)

_FLOW_PREFIX = "publishing:"


def _unprocessable(message: str) -> ChatwootHTTPException:
    return ChatwootHTTPException(status_code=422, detail={"message": message})


def _connectable(network: str) -> PublishingAdapter:
    adapter = adapter_for_network(network)
    if adapter is None or adapter.label is None:
        raise ChatwootHTTPException(
            status_code=404, detail={"message": "Esa red no se conecta desde acá"}
        )
    return adapter


def connectable_networks() -> list[dict[str, Any]]:
    """The networks an owner can connect, and whether the installation is
    ready for each."""
    return [
        {
            "network": adapter.network,
            "label": adapter.label,
            "configured": not adapter.missing_connection_settings(),
        }
        for adapter in connectable_adapters()
    ]


def start_connection(account_id: int, network: str) -> str:
    """The authorization URL the owner's browser goes to. 422 when the
    installation is missing settings for that network."""
    adapter = _connectable(network)
    missing = adapter.missing_connection_settings()
    if missing:
        raise _unprocessable(
            f"Falta configurar {adapter.label}: {', '.join(missing)}. "
            "Cargalos en Ajustes → Instalación."
        )
    state = sign_oauth_state(account_id, flow=f"{_FLOW_PREFIX}{adapter.network}")
    return adapter.authorize_url(
        state=state, redirect_uri=get_settings().publishing_oauth_redirect_uri
    )


def network_of_state(payload: dict[str, Any]) -> str | None:
    """The network a verified state was signed for (``None`` when it wasn't
    signed by :func:`start_connection`)."""
    flow = payload.get("flow")
    if isinstance(flow, str) and flow.startswith(_FLOW_PREFIX):
        return flow.removeprefix(_FLOW_PREFIX)
    return None


async def complete_connection(
    session: AsyncSession, *, account_id: int, network: str, code: str
) -> PublishingChannel:
    """Trade the code for the account and store it as a channel of the
    account (updating the existing one when it was connected before). 422
    with the network's reason when it fails."""
    adapter = _connectable(network)
    try:
        connected = await adapter.complete_authorization(
            code=code, redirect_uri=get_settings().publishing_oauth_redirect_uri
        )
    except ChannelConnectionError as exc:
        raise _unprocessable(str(exc)) from exc
    if not connected.external_id:
        raise _unprocessable(f"{adapter.label} no identificó la cuenta autorizada")

    channel = (
        await session.exec(
            select(PublishingChannel).where(
                PublishingChannel.account_id == account_id,
                PublishingChannel.network == adapter.network,
                PublishingChannel.external_id == connected.external_id,
            )
        )
    ).first()
    if channel is None:
        channel = PublishingChannel(
            account_id=account_id,
            network=adapter.network,
            external_id=connected.external_id,
        )
    channel.name = connected.name
    channel.username = connected.username
    channel.avatar_url = connected.avatar_url
    channel.credentials = connected.credentials
    channel.token_expires_at = connected.token_expires_at
    channel.status = CHANNEL_STATUS_ACTIVE
    channel.status_message = None
    session.add(channel)
    await session.flush()
    return channel


async def delete_channel(session: AsyncSession, *, channel: PublishingChannel) -> None:
    """Disconnect a channel. Its publications' destinations go with it.
    Channels of an inbox are removed by removing the inbox."""
    if channel.inbox_id is not None:
        raise _unprocessable(
            "Este canal es de una bandeja de entrada: se quita desde Ajustes → "
            "Bandejas de entrada"
        )
    await session.delete(channel)
    await session.flush()


async def refresh_expiring_channels(
    session: AsyncSession, *, now: datetime | None = None
) -> int:
    """Renew the credentials of active channels about to expire, committing
    each one. A network that refuses marks the channel for reconnecting.
    Returns how many were renewed."""
    now = now or datetime.now(UTC)
    channel_ids = (
        await session.exec(
            select(PublishingChannel.id).where(
                PublishingChannel.status == CHANNEL_STATUS_ACTIVE,
                col(PublishingChannel.token_expires_at).is_not(None),
                col(PublishingChannel.token_expires_at) < now + REFRESH_BEFORE,
            )
        )
    ).all()
    renewed = 0
    for channel_id in channel_ids:
        try:
            channel = await session.get(PublishingChannel, channel_id)
            adapter = adapter_for_network(channel.network) if channel else None
            if channel is None or adapter is None:
                continue
            try:
                fresh = await adapter.refresh_credentials(channel)
            except ChannelConnectionError as exc:
                await mark_reconnect(session, channel_id, str(exc))  # type: ignore[arg-type]
                fresh = None
            if fresh is not None:
                channel.credentials = fresh.credentials
                channel.token_expires_at = fresh.token_expires_at
                session.add(channel)
                renewed += 1
            await session.commit()
        except Exception:
            # One channel must not sink the rest.
            await session.rollback()
            log.exception("publishing.channels.refresh_failed channel_id=%s", channel_id)
    return renewed


__all__ = [
    "complete_connection",
    "connectable_networks",
    "delete_channel",
    "network_of_state",
    "refresh_expiring_channels",
    "start_connection",
]
