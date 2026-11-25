"""ContactInboxBuilder when another request wins the race.

Meta sends a number's webhooks in parallel. Two of them can look up the
same (inbox, source_id), both find nothing, and both insert: the loser
must use the winner's row and keep its own transaction, instead of a 422
that rolled back the whole webhook batch.
"""

from __future__ import annotations

import pytest
from sqlmodel import select

from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact, ContactInbox
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.teams import models as _teams  # noqa: F401  (mapper)

pytestmark = pytest.mark.integration


async def test_losing_the_race_returns_the_winner_and_keeps_the_transaction(db_session):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="race@contact-inbox.example.com",
            account_name="Race",
            user_full_name="Race",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    inbox = (
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="API",
                channel_type="api",
                channel_params={},
            ),
        ).perform()
    ).inbox
    contact = Contact(account_id=owner.account.id, name="Cliente", phone_number="+59899000111")
    db_session.add(contact)
    await db_session.flush()
    winner = ContactInbox(contact_id=contact.id, inbox_id=inbox.id, source_id="+59899000111")
    db_session.add(winner)
    await db_session.flush()

    builder = ContactInboxBuilder(
        session=db_session, contact=contact, inbox=inbox, source_id="+59899000111"
    )
    # The first lookup happened before the winner committed: it saw nothing.
    real_exec = db_session.exec
    calls = {"n": 0}

    async def first_lookup_misses(stmt, *args, **kwargs):
        calls["n"] += 1
        result = await real_exec(stmt, *args, **kwargs)
        if calls["n"] == 1:
            result.all()  # drain it
            return await real_exec(select(ContactInbox).where(ContactInbox.id == -1))
        return result

    db_session.exec = first_lookup_misses  # type: ignore[method-assign]
    try:
        got = await builder.perform()
    finally:
        db_session.exec = real_exec  # type: ignore[method-assign]

    assert got.id == winner.id
    # The session is still usable: nothing was rolled back.
    still = await db_session.get(Contact, contact.id)
    assert still is not None and still.name == "Cliente"
