"""The auto-reply DM has to land in the agent inbox, not only on Instagram.

Before this, a keyword rule sent the link and left no trace: if the person
answered, the team saw a bare reply with nothing above it, and there was no
way to count how many people the link went out to.
"""

from __future__ import annotations

import pytest
from sqlmodel import select

from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact, ContactInbox
from app.domains.conversations.models import Conversation, Message
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.instagram.autoreply_service import record_private_reply
from app.domains.instagram.incoming import process_instagram_webhook
from app.domains.instagram.models import InstagramComment
from app.domains.teams import models as _teams  # noqa: F401  (mapper)

pytestmark = pytest.mark.integration

IGSID = "IGSID-777"
MID = "MID-777"


async def _seed(db_session, suffix: str, *, ig_id: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@igrec.example.com",
            account_name=f"IGREC{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name=f"IG{suffix}",
            channel_type="instagram",
            channel_params={"instagram_id": ig_id, "access_token": "PAGE-TOKEN"},
        ),
    ).perform()
    comment = InstagramComment(
        account_id=owner.account.id,
        channel_instagram_id=result.channel.id,
        ig_comment_id=f"CMT{suffix}",
        ig_media_id=f"MED{suffix}",
        from_username="fan",
        from_id="COMMENT-SCOPED-ID",
        text="info",
    )
    db_session.add(comment)
    await db_session.flush()
    return owner, result.inbox, result.channel, comment


async def _record(db_session, *, comment, channel, mid=MID, igsid=IGSID):
    return await record_private_reply(
        db_session,
        comment=comment,
        channel=channel,
        text="Acá va el link: ejemplo.com",
        recipient_igsid=igsid,
        message_id=mid,
    )


async def test_the_sent_dm_lands_as_an_outgoing_message(db_session):
    _owner, inbox, channel, comment = await _seed(
        db_session, "-ok", ig_id="IGREC1"
    )

    conversation = await _record(db_session, comment=comment, channel=channel)

    assert conversation is not None
    assert conversation.inbox_id == inbox.id
    msg = (
        await db_session.exec(
            select(Message).where(Message.conversation_id == conversation.id)
        )
    ).one()
    assert msg.content == "Acá va el link: ejemplo.com"
    assert msg.message_type_str == "outgoing"
    assert msg.source_id == MID
    # Nobody on the team wrote it, so nobody is credited with it.
    assert msg.sender_id is None
    assert msg.content_attributes["automation"] == "instagram_comment_autoreply"
    assert msg.content_attributes["instagram_comment_id"] == comment.ig_comment_id


async def test_the_contact_is_keyed_on_the_igsid_meta_returned(db_session):
    """Not on the comment's ``from.id`` — the two are not interchangeable."""
    owner, inbox, channel, comment = await _seed(
        db_session, "-key", ig_id="IGREC2"
    )
    await _record(db_session, comment=comment, channel=channel)

    ci = (
        await db_session.exec(
            select(ContactInbox).where(ContactInbox.inbox_id == inbox.id)
        )
    ).one()
    assert ci.source_id == IGSID
    contact = await db_session.get(Contact, ci.contact_id)
    assert contact is not None
    assert contact.account_id == owner.account.id


async def test_the_comment_points_at_the_thread_it_opened(db_session):
    _owner, _inbox, channel, comment = await _seed(
        db_session, "-link", ig_id="IGREC3"
    )
    conversation = await _record(db_session, comment=comment, channel=channel)
    assert comment.conversation_id == conversation.id


async def test_a_second_reply_continues_the_same_thread(db_session):
    """Two people commenting is two threads; one person twice is one."""
    _owner, _inbox, channel, comment = await _seed(
        db_session, "-same", ig_id="IGREC4"
    )
    first = await _record(db_session, comment=comment, channel=channel)
    second = await _record(
        db_session, comment=comment, channel=channel, mid="MID-OTHER"
    )
    assert second is not None
    assert second.id == first.id
    msgs = (
        await db_session.exec(
            select(Message).where(Message.conversation_id == first.id)
        )
    ).all()
    assert len(msgs) == 2


async def test_a_retried_task_does_not_write_the_reply_twice(db_session):
    _owner, _inbox, channel, comment = await _seed(
        db_session, "-retry", ig_id="IGREC5"
    )
    conversation = await _record(db_session, comment=comment, channel=channel)
    assert await _record(db_session, comment=comment, channel=channel) is None

    msgs = (
        await db_session.exec(
            select(Message).where(Message.conversation_id == conversation.id)
        )
    ).all()
    assert len(msgs) == 1


async def test_metas_echo_of_our_own_reply_is_not_stored_again(db_session):
    """The end that actually bit: Meta echoes outbound sends back at us.

    The inbound path skips a mid it already holds, so stamping the mid on
    the recorded message is what keeps the reply from appearing twice.
    """
    _owner, _inbox, channel, comment = await _seed(
        db_session, "-echo", ig_id="IGREC6"
    )
    conversation = await _record(db_session, comment=comment, channel=channel)

    echo = {
        "object": "instagram",
        "entry": [
            {
                "id": "IGREC6",
                "messaging": [
                    {
                        "sender": {"id": "IGREC6"},
                        "recipient": {"id": IGSID},
                        "message": {
                            "mid": MID,
                            "text": "Acá va el link: ejemplo.com",
                            "is_echo": True,
                        },
                    }
                ],
            }
        ],
    }
    assert await process_instagram_webhook(db_session, payload=echo) == []

    msgs = (
        await db_session.exec(
            select(Message).where(Message.conversation_id == conversation.id)
        )
    ).all()
    assert len(msgs) == 1


async def test_a_reply_meta_gave_no_mid_for_is_still_recorded(db_session):
    """Losing the dedupe key is not a reason to lose the record."""
    _owner, _inbox, channel, comment = await _seed(
        db_session, "-nomid", ig_id="IGREC7"
    )
    conversation = await _record(
        db_session, comment=comment, channel=channel, mid=None
    )
    assert conversation is not None
    msg = (
        await db_session.exec(
            select(Message).where(Message.conversation_id == conversation.id)
        )
    ).one()
    assert msg.source_id is None


async def test_a_later_inbound_dm_joins_the_thread_the_reply_opened(db_session):
    """The whole point: the team reads the answer under the link they sent."""
    _owner, _inbox, channel, comment = await _seed(
        db_session, "-inbound", ig_id="IGREC8"
    )
    conversation = await _record(db_session, comment=comment, channel=channel)

    inbound = {
        "object": "instagram",
        "entry": [
            {
                "id": "IGREC8",
                "messaging": [
                    {
                        "sender": {"id": IGSID},
                        "recipient": {"id": "IGREC8"},
                        "message": {"mid": "MID-REPLY", "text": "gracias!"},
                    }
                ],
            }
        ],
    }
    (msg,) = await process_instagram_webhook(db_session, payload=inbound)
    assert msg.conversation_id == conversation.id
    assert msg.message_type_str == "incoming"

    rows = (
        await db_session.exec(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.id)
        )
    ).all()
    assert [m.message_type_str for m in rows] == ["outgoing", "incoming"]


async def test_nothing_is_written_when_the_channel_has_no_inbox(db_session):
    _owner, inbox, channel, comment = await _seed(
        db_session, "-noinbox", ig_id="IGREC9"
    )
    await db_session.delete(inbox)
    await db_session.flush()

    assert await _record(db_session, comment=comment, channel=channel) is None
    assert (await db_session.exec(select(Conversation))).all() == []
