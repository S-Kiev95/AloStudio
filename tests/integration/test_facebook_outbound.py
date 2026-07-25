"""Integration tests for the Facebook Messenger outbound path.

Uses respx to intercept httpx calls to Meta's Graph API. The real
Graph endpoint is never hit; tests assert the URL, query string,
body shape and the WAMID-equivalent (Meta's ``message_id``) round-
trip stamping on ``messages.source_id``.

Anchors:
  reference/chatwoot/app/services/facebook/send_on_facebook_service.rb
  reference/chatwoot/spec/services/facebook/send_on_facebook_service_spec.rb
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from app.core.config import get_settings
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import (
    MESSAGE_TYPE_OUTGOING,
    Conversation,
    Message,
)
from app.domains.conversations.service import (
    ConversationBuilderParams,
    MessageBuilderParams,
    create_conversation,
    create_message,
)
from app.domains.facebook.sender import send_text_message_facebook
from app.domains.inboxes.models import FacebookPage, Inbox
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams

# Resolve mappers (Conversation.team forward-ref).
from app.domains.teams import models as _teams  # noqa: F401
from app.domains.users.models import User

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------
async def _seed(
    db_session,
    *,
    suffix: str,
    psid: str = "USER_PSID_42",
    page_id: str = "P-OUT",
    page_token: str = "EAAxxxx-page",
) -> tuple[FacebookPage, Inbox, Conversation, User]:
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@fbout.example.com",
            account_name=f"FBOut{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="FB Page",
            channel_type="facebook",
            channel_params={
                "page_id": page_id,
                "page_access_token": page_token,
            },
        ),
    ).perform()
    assert isinstance(result.channel, FacebookPage)

    contact = Contact(
        account_id=owner.account.id,
        name="Diana",
    )
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session,
        contact=contact,
        inbox=result.inbox,
        source_id=psid,
    ).perform()
    conv = await create_conversation(
        db_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(),
    )
    return result.channel, result.inbox, conv, owner.user


def _expected_url(channel: FacebookPage) -> str:
    settings = get_settings()
    return (
        f"https://graph.facebook.com/{settings.facebook_api_version}"
        f"/me/messages?access_token={channel.page_access_token}"
    )


# ---------------------------------------------------------------------------
# send_text_message_facebook — direct
# ---------------------------------------------------------------------------
@respx.mock
async def test_send_text_posts_canonical_body(db_session):
    channel, inbox, conv, user = await _seed(db_session, suffix="-shape")
    msg = Message(
        account_id=channel.account_id,
        inbox_id=inbox.id,
        conversation_id=conv.id,
        message_type=MESSAGE_TYPE_OUTGOING,
        content_type=0,
        content="hi from Chatwoot",
        sender_type="User",
        sender_id=user.id,
        private=False,
    )
    db_session.add(msg)
    await db_session.flush()

    route = respx.post(_expected_url(channel)).mock(
        return_value=httpx.Response(
            200,
            json={"recipient_id": "USER_PSID_42", "message_id": "mid.out-1"},
        )
    )

    ok = await send_text_message_facebook(
        db_session,
        channel=channel,
        message=msg,
        to_psid="USER_PSID_42",
    )
    assert ok is True
    assert route.called
    body = json.loads(route.calls.last.request.content)
    assert body == {
        "recipient": {"id": "USER_PSID_42"},
        "message": {"text": "hi from Chatwoot"},
        "messaging_type": "MESSAGE_TAG",
        "tag": "ACCOUNT_UPDATE",
    }
    await db_session.refresh(msg)
    assert msg.source_id == "mid.out-1"


@respx.mock
async def test_send_text_4xx_returns_false_no_stamp(db_session):
    channel, inbox, conv, user = await _seed(db_session, suffix="-fail")
    msg = Message(
        account_id=channel.account_id,
        inbox_id=inbox.id,
        conversation_id=conv.id,
        message_type=MESSAGE_TYPE_OUTGOING,
        content_type=0,
        content="will fail",
        sender_type="User",
        sender_id=user.id,
        private=False,
    )
    db_session.add(msg)
    await db_session.flush()
    pre = msg.source_id

    respx.post(_expected_url(channel)).mock(
        return_value=httpx.Response(
            400,
            json={
                "error": {
                    "message": "Invalid OAuth access token.",
                    "type": "OAuthException",
                    "code": 190,
                }
            },
        )
    )
    ok = await send_text_message_facebook(
        db_session,
        channel=channel,
        message=msg,
        to_psid="USER_PSID_42",
    )
    assert ok is False
    await db_session.refresh(msg)
    assert msg.source_id == pre


@respx.mock
async def test_send_text_transport_error_returns_false(db_session):
    """ConnectError raised by httpx is swallowed + returns False —
    must never propagate to the caller."""
    channel, inbox, conv, user = await _seed(db_session, suffix="-net")
    msg = Message(
        account_id=channel.account_id,
        inbox_id=inbox.id,
        conversation_id=conv.id,
        message_type=MESSAGE_TYPE_OUTGOING,
        content_type=0,
        content="net dies",
        sender_type="User",
        sender_id=user.id,
        private=False,
    )
    db_session.add(msg)
    await db_session.flush()

    respx.post(_expected_url(channel)).mock(
        side_effect=httpx.ConnectError("dns fail")
    )
    ok = await send_text_message_facebook(
        db_session, channel=channel, message=msg, to_psid="USER_PSID_42"
    )
    assert ok is False


@respx.mock
async def test_send_text_skips_when_no_psid(db_session):
    channel, inbox, conv, user = await _seed(db_session, suffix="-nopsid")
    msg = Message(
        account_id=channel.account_id,
        inbox_id=inbox.id,
        conversation_id=conv.id,
        message_type=MESSAGE_TYPE_OUTGOING,
        content_type=0,
        content="x",
        sender_type="User",
        sender_id=user.id,
        private=False,
    )
    db_session.add(msg)
    await db_session.flush()

    route = respx.post(_expected_url(channel)).mock(
        return_value=httpx.Response(200, json={"message_id": "x"})
    )
    ok = await send_text_message_facebook(
        db_session, channel=channel, message=msg, to_psid=""
    )
    assert ok is False
    assert not route.called


# ---------------------------------------------------------------------------
# Full create_message cascade
# ---------------------------------------------------------------------------
@respx.mock
async def test_outgoing_message_via_create_message_hits_graph(db_session):
    """Creating an outgoing Message on a Channel::FacebookPage inbox
    via ``create_message`` triggers the Graph send through the post-
    create cascade. The PSID gets resolved from ContactInbox.source_id."""
    channel, _inbox, conv, user = await _seed(
        db_session, suffix="-cascade", psid="PSID-CASCADE"
    )

    route = respx.post(_expected_url(channel)).mock(
        return_value=httpx.Response(
            200,
            json={"recipient_id": "PSID-CASCADE", "message_id": "mid.cascade"},
        )
    )
    msg = await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(
            content="from cascade",
            message_type="outgoing",
        ),
        user_id=user.id,
    )
    assert msg is not None
    assert route.called
    body = json.loads(route.calls.last.request.content)
    assert body["recipient"] == {"id": "PSID-CASCADE"}
    assert body["message"]["text"] == "from cascade"

    await db_session.refresh(msg)
    assert msg.source_id == "mid.cascade"
