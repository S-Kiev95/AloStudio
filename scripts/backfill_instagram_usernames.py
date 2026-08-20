"""Repair Instagram channels against what Meta says about each token.

    PYTHONPATH=. python scripts/backfill_instagram_usernames.py [--apply]

Two things drift on a channel connected before 2026-08-20:

1. **The inbox name.** Every inbox the Instagram-Login flow created was
   called "Instagram", so an account with more than one is a list of
   identical rows with no way to tell which is which.

2. **The stored id.** The Instagram-Login token exchange hands back an
   *app-scoped* id (``28005…``); webhooks arrive under the account's
   canonical id (``17841…``), which is what ``_resolve_channel`` matches.
   A channel holding the app-scoped one publishes and sends fine and
   silently receives nothing.

Only placeholder names are touched — a name an admin chose is left alone.
Runs as a dry run unless ``--apply`` is passed.

Nothing is ever merged or deleted. Two channels that resolve to the same
account, or a repair that would collide with an existing row, are
reported for a human: the webhook routes by id so only one can receive,
and dropping the other takes its conversations with it.
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
        ids_in_use = {c.instagram_id: c.id for c in channels}

        seen: dict[str, list[int]] = defaultdict(list)
        renamed = 0
        repaired = 0

        for channel in channels:
            setting = settings.get(channel.id)
            login_type = setting.login_type if setting else "facebook"
            inbox = inboxes.get(channel.id)
            label = f"canal {channel.id} (cuenta {channel.account_id})"

            canonical, username = await oauth.fetch_profile(
                instagram_id=channel.instagram_id,
                access_token=channel.access_token,
                login_type=login_type,
            )
            if canonical is None and username is None:
                print(f"{label}: Meta no respondió — token vencido o revocado")
                continue

            if username:
                seen[username].append(channel.id)

            # --- the id webhooks arrive under ---------------------------
            if canonical and canonical != channel.instagram_id:
                collision = ids_in_use.get(canonical)
                if collision is not None and collision != channel.id:
                    print(
                        f"{label}: guarda {channel.instagram_id} pero le "
                        f"corresponde {canonical}, que ya usa el canal "
                        f"{collision}. Sin tocar — decidí cuál conservar."
                    )
                else:
                    print(
                        f"{label}: id {channel.instagram_id} (app-scoped) "
                        f"-> {canonical} (canónico, el de los webhooks)"
                    )
                    repaired += 1
                    if apply:
                        del ids_in_use[channel.instagram_id]
                        channel.instagram_id = canonical
                        ids_in_use[canonical] = channel.id
                        session.add(channel)

            # --- the name in the list -----------------------------------
            if inbox is None:
                print(f"{label}: sin bandeja asociada")
                continue
            if not username:
                print(f"{label}: Meta no dio el handle, nombre sin cambios")
                continue
            if not _is_placeholder_name(inbox.name):
                print(f"{label}: @{username}, conserva su nombre {inbox.name!r}")
                continue

            print(f"{label}: nombre {inbox.name!r} -> {username!r}")
            renamed += 1
            if apply:
                inbox.name = username
                session.add(inbox)

        if apply and (renamed or repaired):
            await session.commit()

        print()
        for username, channel_ids in sorted(seen.items()):
            if len(channel_ids) > 1:
                print(
                    f"AVISO: @{username} está en {len(channel_ids)} canales "
                    f"({', '.join(map(str, channel_ids))}). Sólo uno recibe "
                    f"los webhooks; revisá cuál conservar."
                )

        verb = "Listo" if apply else "Ensayo"
        print(f"\n{verb}: {repaired} id(s) y {renamed} nombre(s).")
        if not apply and (repaired or renamed):
            print("Repetí con --apply para escribirlos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main("--apply" in sys.argv)))
