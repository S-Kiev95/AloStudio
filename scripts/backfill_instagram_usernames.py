"""Name Instagram inboxes after the account they actually hold.

    PYTHONPATH=. python scripts/backfill_instagram_usernames.py [--apply]

Every inbox the Instagram Login flow created before this was called
"Instagram", so an account with more than one is a list of identical rows
and no way to tell which is which. This asks each stored token who it
belongs to and renames its inbox to the handle.

Only placeholder names are touched — a name an admin chose is left alone.
Runs as a dry run unless ``--apply`` is passed.

Duplicates are reported, never merged: two channels whose tokens resolve
to the *same* Instagram id means one of them is dead weight (the webhook
resolves a channel by id, so only one of them ever receives anything).
Deciding which to drop takes its conversations with it, so that is a
human's call.
"""

from __future__ import annotations

import asyncio
import sys
from collections import defaultdict

from sqlmodel import select

import app.main  # noqa: F401  — closes the SQLAlchemy mapper registry
from app.core.db import get_session_factory
from app.domains.inboxes.models import (
    CHANNEL_TYPE_INSTAGRAM,
    Inbox,
    InstagramChannel,
)
from app.domains.instagram import oauth
from app.domains.instagram.connect_service import _is_placeholder_name
from app.domains.instagram.models import InstagramChannelSetting


async def main(apply: bool) -> int:
    factory = get_session_factory()
    async with factory() as session:
        channels = list((await session.exec(select(InstagramChannel))).all())
        settings = {
            s.channel_instagram_id: s
            for s in (await session.exec(select(InstagramChannelSetting))).all()
        }
        inboxes = {
            i.channel_id: i
            for i in (
                await session.exec(
                    select(Inbox).where(
                        Inbox.channel_type == CHANNEL_TYPE_INSTAGRAM
                    )
                )
            ).all()
        }

        seen: dict[str, list[int]] = defaultdict(list)
        renamed = 0

        for channel in channels:
            setting = settings.get(channel.id)
            login_type = setting.login_type if setting else "facebook"
            inbox = inboxes.get(channel.id)
            label = f"canal {channel.id} (cuenta {channel.account_id})"

            username = await oauth.fetch_username(
                instagram_id=channel.instagram_id,
                access_token=channel.access_token,
                login_type=login_type,
            )
            if username is None:
                print(f"{label}: Meta no respondió — token vencido o revocado")
                continue

            seen[username].append(channel.id)

            if inbox is None:
                print(f"{label}: @{username}, sin bandeja asociada")
                continue
            if not _is_placeholder_name(inbox.name):
                print(f"{label}: @{username}, conserva su nombre {inbox.name!r}")
                continue

            print(f"{label}: {inbox.name!r} -> {username!r}")
            renamed += 1
            if apply:
                inbox.name = username
                session.add(inbox)

        if apply and renamed:
            await session.commit()

        print()
        for username, channel_ids in sorted(seen.items()):
            if len(channel_ids) > 1:
                print(
                    f"AVISO: @{username} está en {len(channel_ids)} canales "
                    f"({', '.join(map(str, channel_ids))}). Sólo uno recibe "
                    f"los webhooks; revisá cuál conservar."
                )

        if not apply:
            print(f"\nEnsayo: {renamed} bandeja(s) a renombrar. Repetí con --apply.")
        else:
            print(f"\nListo: {renamed} bandeja(s) renombrada(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main("--apply" in sys.argv)))
