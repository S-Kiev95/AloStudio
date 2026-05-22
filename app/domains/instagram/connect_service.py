"""Instagram connection service (I.10).

Connection capability tracking + the manual ("paste a token") connect
path. The OAuth flows (Facebook Login + Instagram Login) layer their
token-exchange on top of :func:`record_connection` once they have a
page/IG token.

Capability model: a ``channel_instagram`` row gets a 1:1
``instagram_channel_settings`` row recording ``login_type``. DELETE media
is only available on Facebook Login (verified against Meta docs), so the
delete path gates on :func:`can_delete_media`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import ChatwootHTTPException
from app.domains.instagram.models import (
    INSTAGRAM_CONNECT_METHODS,
    INSTAGRAM_LOGIN_TYPES,
    InstagramChannelSetting,
)


async def get_channel_setting(
    session: AsyncSession, *, channel_instagram_id: int
) -> InstagramChannelSetting | None:
    return (
        await session.exec(
            select(InstagramChannelSetting).where(
                InstagramChannelSetting.channel_instagram_id
                == channel_instagram_id
            )
        )
    ).first()


async def record_connection(
    session: AsyncSession,
    *,
    channel_instagram_id: int,
    login_type: str,
    connect_method: str = "manual",
    page_id: str | None = None,
) -> InstagramChannelSetting:
    """Upsert the settings row for a channel (idempotent on
    channel_instagram_id)."""
    if login_type not in INSTAGRAM_LOGIN_TYPES:
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": (
                    f"login_type must be one of "
                    f"{', '.join(INSTAGRAM_LOGIN_TYPES)}"
                )
            },
        )
    if connect_method not in INSTAGRAM_CONNECT_METHODS:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "invalid connect_method"},
        )
    existing = await get_channel_setting(
        session, channel_instagram_id=channel_instagram_id
    )
    if existing is not None:
        existing.login_type = login_type
        existing.connect_method = connect_method
        if page_id is not None:
            existing.page_id = page_id
        session.add(existing)
        await session.flush()
        await session.refresh(existing)
        return existing
    row = InstagramChannelSetting(
        channel_instagram_id=channel_instagram_id,
        login_type=login_type,
        connect_method=connect_method,
        page_id=page_id,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def can_delete_media(
    session: AsyncSession, *, channel_instagram_id: int
) -> bool:
    """True when the channel's connection supports DELETE media.

    Facebook Login → yes. Instagram Login → no (Meta API limitation).
    A channel with no settings row (legacy / pre-I.10) defaults to
    *allowed* — those were created via the Phase 5e Facebook-page path.
    """
    setting = await get_channel_setting(
        session, channel_instagram_id=channel_instagram_id
    )
    if setting is None:
        return True
    return setting.login_type != "instagram"


async def connect_manual(
    session: AsyncSession,
    *,
    account: Any,
    name: str,
    instagram_id: str,
    access_token: str,
    login_type: str,
    expires_at: datetime | str | None = None,
) -> dict[str, Any]:
    """Advanced/manual connect: create an Instagram inbox + channel from
    a pasted token (e.g. a permanent System User token) and record the
    ``login_type``.

    Returns ``{inbox_id, channel_instagram_id, instagram_id,
    login_type}``.
    """
    if login_type not in INSTAGRAM_LOGIN_TYPES:
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": (
                    f"login_type must be one of "
                    f"{', '.join(INSTAGRAM_LOGIN_TYPES)}"
                )
            },
        )
    from app.domains.inboxes.service import (
        InboxBuilder,
        InboxBuilderParams,
    )

    channel_params: dict[str, Any] = {
        "instagram_id": instagram_id,
        "access_token": access_token,
    }
    if expires_at is not None:
        channel_params["expires_at"] = (
            expires_at.isoformat()
            if isinstance(expires_at, datetime)
            else expires_at
        )
    result = await InboxBuilder(
        session,
        InboxBuilderParams(
            account=account,
            name=name,
            channel_type="instagram",
            channel_params=channel_params,
        ),
    ).perform()

    await record_connection(
        session,
        channel_instagram_id=result.channel.id,
        login_type=login_type,
        connect_method="manual",
    )
    return {
        "inbox_id": result.inbox.id,
        "channel_instagram_id": result.channel.id,
        "instagram_id": result.channel.instagram_id,
        "login_type": login_type,
    }


__all__ = [
    "can_delete_media",
    "connect_manual",
    "get_channel_setting",
    "record_connection",
]
