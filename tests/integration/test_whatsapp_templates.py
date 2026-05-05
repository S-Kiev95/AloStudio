"""Integration tests for WhatsApp template sync + send.

Both providers (Cloud + 360dialog) get exercised via respx mocks.
We assert:
  * The right URL is hit for each provider.
  * The body shape matches Rails' ``template_body_parameters``
    (``language.policy=deterministic``, ``components`` array).
  * Sync stores the fetched templates under
    ``WhatsappChannel.message_templates`` + bumps the
    ``message_templates_last_updated`` timestamp.
  * Sync handles Cloud pagination (``paging.next``) by walking the
    chain and concatenating each page's ``data``.

Anchors:
  reference/chatwoot/app/services/whatsapp/providers/whatsapp_cloud_service.rb
  reference/chatwoot/app/services/whatsapp/providers/whatsapp_360_dialog_service.rb
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx

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
    create_conversation,
)
from app.domains.inboxes.models import (
    WHATSAPP_PROVIDER_360DIALOG,
    WHATSAPP_PROVIDER_CLOUD,
    Inbox,
    WhatsappChannel,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.domains.users.models import User
from app.domains.whatsapp.templates import (
    send_template_message,
    sync_templates,
    template_body_parameters,
)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------
async def _seed_cloud(
    db_session, *, suffix: str
) -> tuple[WhatsappChannel, Inbox, Conversation, User]:
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@watc.example.com",
            account_name=f"WATC{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="WA Cloud",
            channel_type="whatsapp",
            channel_params={
                "phone_number": f"+155566{suffix.lstrip('-').rjust(5, '0')[:5]}",
                "provider": WHATSAPP_PROVIDER_CLOUD,
                "provider_config": {
                    "api_key": "EAAxxxx",
                    "phone_number_id": "PID-1",
                    "business_account_id": "BAID-1",
                },
            },
        ),
    ).perform()
    contact = Contact(
        account_id=owner.account.id,
        phone_number="+5551234567",
        name="Diana",
    )
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session,
        contact=contact,
        inbox=result.inbox,
        source_id="+5551234567",
    ).perform()
    conv = await create_conversation(
        db_session, contact_inbox=ci, params=ConversationBuilderParams()
    )
    return result.channel, result.inbox, conv, owner.user


async def _seed_360dialog(
    db_session, *, suffix: str
) -> tuple[WhatsappChannel, Inbox, Conversation, User]:
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@wat3.example.com",
            account_name=f"WAT3{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="WA 360",
            channel_type="whatsapp",
            channel_params={
                "phone_number": f"+155578{suffix.lstrip('-').rjust(5, '0')[:5]}",
                "provider": WHATSAPP_PROVIDER_360DIALOG,
                "provider_config": {
                    "api_key": "360d-secret",
                    "url": "https://waba-sandbox.360dialog.io/v1",
                },
            },
        ),
    ).perform()
    contact = Contact(
        account_id=owner.account.id,
        phone_number="+5557654321",
        name="Eduardo",
    )
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session,
        contact=contact,
        inbox=result.inbox,
        source_id="+5557654321",
    ).perform()
    conv = await create_conversation(
        db_session, contact_inbox=ci, params=ConversationBuilderParams()
    )
    return result.channel, result.inbox, conv, owner.user


# ---------------------------------------------------------------------------
# template_body_parameters — pure function
# ---------------------------------------------------------------------------
def test_template_body_uses_deterministic_language_policy() -> None:
    out = template_body_parameters(
        {
            "name": "order_shipped",
            "lang_code": "en_US",
            "parameters": [
                {"type": "body", "parameters": [{"type": "text", "text": "Bob"}]},
            ],
        }
    )
    assert out == {
        "name": "order_shipped",
        "language": {"policy": "deterministic", "code": "en_US"},
        "components": [
            {"type": "body", "parameters": [{"type": "text", "text": "Bob"}]},
        ],
    }


def test_template_body_defaults_components_to_empty_list() -> None:
    """Mirror Rails ``template_info[:parameters] || []``."""
    out = template_body_parameters(
        {"name": "hello", "lang_code": "es_AR"}
    )
    assert out["components"] == []


# ---------------------------------------------------------------------------
# Send template — Cloud
# ---------------------------------------------------------------------------
@respx.mock
async def test_send_template_cloud_posts_canonical_body(db_session):
    channel, inbox, conv, user = await _seed_cloud(db_session, suffix="-c1")
    msg = Message(
        account_id=channel.account_id,
        inbox_id=inbox.id,
        conversation_id=conv.id,
        message_type=MESSAGE_TYPE_OUTGOING,
        content_type=0,
        content="(template content)",
        sender_type="User",
        sender_id=user.id,
        private=False,
    )
    db_session.add(msg)
    await db_session.flush()

    route = respx.post(
        "https://graph.facebook.com/v13.0/PID-1/messages"
    ).mock(
        return_value=httpx.Response(
            200, json={"messages": [{"id": "wamid.template-out"}]}
        )
    )
    ok = await send_template_message(
        db_session,
        channel=channel,
        message=msg,
        to_phone="5551234567",
        template_info={
            "name": "order_shipped",
            "lang_code": "en_US",
            "parameters": [
                {"type": "body", "parameters": [{"type": "text", "text": "Bob"}]}
            ],
        },
    )
    assert ok is True
    body = json.loads(route.calls.last.request.content)
    assert body["messaging_product"] == "whatsapp"
    assert body["recipient_type"] == "individual"
    assert body["to"] == "5551234567"
    assert body["type"] == "template"
    assert body["template"]["name"] == "order_shipped"
    assert body["template"]["language"] == {
        "policy": "deterministic",
        "code": "en_US",
    }
    await db_session.refresh(msg)
    assert msg.source_id == "wamid.template-out"


# ---------------------------------------------------------------------------
# Send template — 360dialog
# ---------------------------------------------------------------------------
@respx.mock
async def test_send_template_360dialog_omits_messaging_product(db_session):
    channel, inbox, conv, user = await _seed_360dialog(db_session, suffix="-d1")
    msg = Message(
        account_id=channel.account_id,
        inbox_id=inbox.id,
        conversation_id=conv.id,
        message_type=MESSAGE_TYPE_OUTGOING,
        content_type=0,
        content="(template content)",
        sender_type="User",
        sender_id=user.id,
        private=False,
    )
    db_session.add(msg)
    await db_session.flush()

    route = respx.post(
        "https://waba-sandbox.360dialog.io/v1/messages"
    ).mock(
        return_value=httpx.Response(
            200, json={"messages": [{"id": "gB-template"}]}
        )
    )
    ok = await send_template_message(
        db_session,
        channel=channel,
        message=msg,
        to_phone="5557654321",
        template_info={
            "name": "order_shipped",
            "lang_code": "es_AR",
            "parameters": [],
        },
    )
    assert ok is True
    request = route.calls.last.request
    assert request.headers.get("d360-api-key") == "360d-secret"
    body = json.loads(request.content)
    # 360dialog body has NO ``messaging_product`` field — that's
    # Meta-Cloud-only.
    assert "messaging_product" not in body
    assert body["type"] == "template"
    assert body["template"]["name"] == "order_shipped"
    await db_session.refresh(msg)
    assert msg.source_id == "gB-template"


# ---------------------------------------------------------------------------
# Sync — Cloud, single page
# ---------------------------------------------------------------------------
@respx.mock
async def test_sync_cloud_single_page_stores_templates(db_session):
    channel, _inbox, _conv, _user = await _seed_cloud(db_session, suffix="-s1")
    pre_stamp = channel.message_templates_last_updated
    assert pre_stamp is None

    payload: dict[str, Any] = {
        "data": [
            {
                "name": "order_shipped",
                "language": "en_US",
                "status": "APPROVED",
                "components": [],
            },
            {
                "name": "appointment_reminder",
                "language": "en_US",
                "status": "APPROVED",
                "components": [],
            },
        ],
        "paging": {},
    }
    respx.get(
        "https://graph.facebook.com/v14.0/BAID-1/message_templates"
    ).mock(return_value=httpx.Response(200, json=payload))

    n = await sync_templates(db_session, channel=channel)
    assert n == 2
    await db_session.refresh(channel)
    names = sorted(t["name"] for t in channel.message_templates)
    assert names == ["appointment_reminder", "order_shipped"]
    # Timestamp bumped regardless of success — but here it's set.
    assert channel.message_templates_last_updated is not None


@respx.mock
async def test_sync_cloud_walks_paging_next(db_session):
    """Cloud paginates ``data`` 25 at a time; Rails recurses via
    ``paging.next``. We assert both pages are concatenated."""
    channel, _inbox, _conv, _user = await _seed_cloud(db_session, suffix="-s2")
    page_1 = {
        "data": [{"name": "t1", "language": "en_US", "components": []}],
        "paging": {
            "next": "https://graph.facebook.com/v14.0/BAID-1/message_templates?after=cursor1"
        },
    }
    page_2 = {
        "data": [{"name": "t2", "language": "en_US", "components": []}],
        "paging": {},
    }
    respx.get(
        "https://graph.facebook.com/v14.0/BAID-1/message_templates"
    ).mock(side_effect=[
        httpx.Response(200, json=page_1),
        httpx.Response(200, json=page_2),
    ])

    n = await sync_templates(db_session, channel=channel)
    assert n == 2
    await db_session.refresh(channel)
    names = sorted(t["name"] for t in channel.message_templates)
    assert names == ["t1", "t2"]


@respx.mock
async def test_sync_cloud_4xx_keeps_existing_list(db_session):
    """A failed sync bumps the timestamp but leaves the existing
    templates list untouched — Rails' ``update if templates.present?``
    short-circuit."""
    channel, _inbox, _conv, _user = await _seed_cloud(db_session, suffix="-s3")
    # Pre-seed a stored template so we can verify it survives the
    # failed sync.
    channel.message_templates = [{"name": "existing"}]
    db_session.add(channel)
    await db_session.flush()

    respx.get(
        "https://graph.facebook.com/v14.0/BAID-1/message_templates"
    ).mock(return_value=httpx.Response(401, json={"error": {"message": "bad"}}))

    n = await sync_templates(db_session, channel=channel)
    assert n == 0
    await db_session.refresh(channel)
    # Existing list survived.
    assert channel.message_templates == [{"name": "existing"}]
    # But timestamp bumped — we did try.
    assert channel.message_templates_last_updated is not None


# ---------------------------------------------------------------------------
# Sync — 360dialog
# ---------------------------------------------------------------------------
@respx.mock
async def test_sync_360dialog_stores_waba_templates(db_session):
    channel, _inbox, _conv, _user = await _seed_360dialog(
        db_session, suffix="-d2"
    )
    payload = {
        "waba_templates": [
            {
                "name": "welcome",
                "language": "es_AR",
                "components": [
                    {"type": "BODY", "text": "Hola, {{1}}!"},
                ],
            },
            {
                "name": "verification",
                "language": "en_US",
                "components": [],
            },
        ]
    }
    route = respx.get(
        "https://waba-sandbox.360dialog.io/v1/configs/templates"
    ).mock(return_value=httpx.Response(200, json=payload))

    n = await sync_templates(db_session, channel=channel)
    assert n == 2
    assert route.called
    # 360dialog auth header.
    assert (
        route.calls.last.request.headers.get("d360-api-key")
        == "360d-secret"
    )
    await db_session.refresh(channel)
    names = sorted(t["name"] for t in channel.message_templates)
    assert names == ["verification", "welcome"]
