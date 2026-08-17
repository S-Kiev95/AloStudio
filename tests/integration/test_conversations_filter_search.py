"""Integration tests for ``GET /conversations/search`` +
``POST /conversations/filter`` + the index endpoint's new filter
parameters (inbox_id / team_id / labels / q).

Anchors:
  * ``Api::V1::Accounts::ConversationsController#search``/``#filter``
  * ``Conversations::FilterService`` + ``FilterService``
  * ``ConversationFinder``
  * ``filter.json.jbuilder`` / ``search.json.jbuilder`` (both share the
    ``{meta, payload}`` shape).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import (
    CONTENT_TYPE_TEXT,
    CONVERSATION_PRIORITY_URGENT,
    CONVERSATION_STATUS_RESOLVED,
    MESSAGE_TYPE_INCOMING,
    Conversation,
    Message,
)
from app.domains.conversations.service import (
    ConversationBuilderParams,
    create_conversation,
    update_labels,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.main import app

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures (mirror tests/integration/test_conversations_router.py)
# ---------------------------------------------------------------------------
@pytest.fixture
async def client(db_session) -> AsyncIterator[AsyncClient]:
    async def _override() -> AsyncIterator:
        yield db_session

    app.dependency_overrides[get_session] = _override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_session, None)


async def _mint_headers(db_session, user) -> dict[str, str]:
    headers, new_tokens = create_new_auth_token(
        user_tokens=user.tokens, uid=user.uid
    )
    user.tokens = new_tokens
    db_session.add(user)
    await db_session.flush()
    return headers.as_response_headers()


@pytest.fixture
async def seeded(db_session):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="admin@flt.example.com",
            account_name="Filter Inc",
            user_full_name="Admin Filter",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    inbox_a = (
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="API A",
                channel_type="api",
                channel_params={"webhook_url": "https://a.example.com/h"},
            ),
        ).perform()
    ).inbox
    inbox_b = (
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="API B",
                channel_type="api",
                channel_params={"webhook_url": "https://b.example.com/h"},
            ),
        ).perform()
    ).inbox
    contact = Contact(
        account_id=owner.account.id,
        email="c@flt.example.com",
        name="Filter Contact",
    )
    db_session.add(contact)
    await db_session.flush()
    ci_a = await ContactInboxBuilder(
        session=db_session, contact=contact, inbox=inbox_a
    ).perform()
    ci_b = await ContactInboxBuilder(
        session=db_session, contact=contact, inbox=inbox_b
    ).perform()
    admin_h = await _mint_headers(db_session, owner.user)
    return owner, inbox_a, inbox_b, contact, ci_a, ci_b, admin_h


async def _make_conv(db_session, *, contact_inbox, **overrides) -> Conversation:
    conv = await create_conversation(
        db_session,
        contact_inbox=contact_inbox,
        params=ConversationBuilderParams(),
    )
    for k, v in overrides.items():
        setattr(conv, k, v)
    db_session.add(conv)
    await db_session.flush()
    await db_session.refresh(conv)
    return conv


async def _add_message(
    db_session, *, conv: Conversation, content: str, message_type: int
) -> Message:
    msg = Message(
        account_id=conv.account_id,
        inbox_id=conv.inbox_id,
        conversation_id=conv.id,
        message_type=message_type,
        content_type=CONTENT_TYPE_TEXT,
        content=content,
        private=False,
    )
    db_session.add(msg)
    await db_session.flush()
    await db_session.refresh(msg)
    return msg


# ---------------------------------------------------------------------------
# Index — new filter parameters
# ---------------------------------------------------------------------------
async def test_index_filters_by_inbox_id(client, seeded, db_session):
    owner, _inbox_a, inbox_b, _, ci_a, ci_b, admin_h = seeded
    await _make_conv(db_session, contact_inbox=ci_a)
    await _make_conv(db_session, contact_inbox=ci_b)

    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/conversations?inbox_id={inbox_b.id}",
        headers=admin_h,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]["payload"]) == 1
    assert body["data"]["payload"][0]["inbox_id"] == inbox_b.id


async def test_index_filters_by_labels(client, seeded, db_session):
    owner, _, _, _, ci_a, _, admin_h = seeded
    a = await _make_conv(db_session, contact_inbox=ci_a)
    b = await _make_conv(db_session, contact_inbox=ci_a)
    await update_labels(db_session, conversation=a, titles=["urgent"])
    await update_labels(db_session, conversation=b, titles=["billing"])

    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/conversations?labels=urgent",
        headers=admin_h,
    )
    assert resp.status_code == 200
    payload = resp.json()["data"]["payload"]
    assert {c["id"] for c in payload} == {a.display_id}


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
async def test_search_matches_message_content(client, seeded, db_session):
    owner, _, _, _, ci_a, _, admin_h = seeded
    a = await _make_conv(db_session, contact_inbox=ci_a)
    b = await _make_conv(db_session, contact_inbox=ci_a)
    await _add_message(
        db_session, conv=a, content="Need help with billing", message_type=MESSAGE_TYPE_INCOMING
    )
    await _add_message(
        db_session, conv=b, content="Shipping address change", message_type=MESSAGE_TYPE_INCOMING
    )

    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/conversations/search?q=billing",
        headers=admin_h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # search.json.jbuilder envelope: top-level meta + payload, no ``data`` wrap.
    assert "meta" in body
    assert "payload" in body
    assert {c["id"] for c in body["payload"]} == {a.display_id}


async def test_search_skips_default_status_filter(client, seeded, db_session):
    """Mirrors ``unless params[:q]`` in the finder — search returns a
    resolved conversation that the index would've filtered out."""
    owner, _, _, _, ci_a, _, admin_h = seeded
    a = await _make_conv(
        db_session,
        contact_inbox=ci_a,
        status=CONVERSATION_STATUS_RESOLVED,
    )
    await _add_message(
        db_session, conv=a, content="Refund request", message_type=MESSAGE_TYPE_INCOMING
    )
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/conversations/search?q=refund",
        headers=admin_h,
    )
    assert resp.status_code == 200
    payload = resp.json()["payload"]
    assert {c["id"] for c in payload} == {a.display_id}


async def test_search_skips_activity_messages(client, seeded, db_session):
    """Search restricts to incoming/outgoing — activity rows shouldn't
    match (mirrors Rails' ``where(messages: { message_type: allowed })``)."""
    from app.domains.conversations.activities import create_activity_message

    owner, _, _, _, ci_a, _, admin_h = seeded
    a = await _make_conv(db_session, contact_inbox=ci_a)
    # Activity row containing the search term — must NOT match.
    await create_activity_message(
        db_session,
        conversation=a,
        content="Admin changed urgent",
    )

    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/conversations/search?q=urgent",
        headers=admin_h,
    )
    assert resp.status_code == 200
    assert resp.json()["payload"] == []


# ---------------------------------------------------------------------------
# Filter DSL
# ---------------------------------------------------------------------------
async def test_filter_status_equal_to(client, seeded, db_session):
    owner, _, _, _, ci_a, _, admin_h = seeded
    await _make_conv(db_session, contact_inbox=ci_a)
    resolved = await _make_conv(
        db_session, contact_inbox=ci_a, status=CONVERSATION_STATUS_RESOLVED
    )

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/filter",
        json={
            "payload": [
                {
                    "attribute_key": "status",
                    "filter_operator": "equal_to",
                    "values": ["resolved"],
                    "query_operator": None,
                }
            ]
        },
        headers=admin_h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert {c["id"] for c in body["payload"]} == {resolved.display_id}


async def test_filter_priority_is_present(client, seeded, db_session):
    owner, _, _, _, ci_a, _, admin_h = seeded
    has_pri = await _make_conv(
        db_session, contact_inbox=ci_a, priority=CONVERSATION_PRIORITY_URGENT
    )
    await _make_conv(db_session, contact_inbox=ci_a)

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/filter",
        json={
            "payload": [
                {
                    "attribute_key": "priority",
                    "filter_operator": "is_present",
                    "values": [],
                }
            ]
        },
        headers=admin_h,
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()["payload"]
    assert {c["id"] for c in payload} == {has_pri.display_id}


async def test_filter_labels_equal_to(client, seeded, db_session):
    owner, _, _, _, ci_a, _, admin_h = seeded
    a = await _make_conv(db_session, contact_inbox=ci_a)
    b = await _make_conv(db_session, contact_inbox=ci_a)
    await update_labels(db_session, conversation=a, titles=["urgent", "billing"])
    await update_labels(db_session, conversation=b, titles=["other"])

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/filter",
        json={
            "payload": [
                {
                    "attribute_key": "labels",
                    "filter_operator": "equal_to",
                    "values": ["urgent"],
                }
            ]
        },
        headers=admin_h,
    )
    assert resp.status_code == 200
    payload = resp.json()["payload"]
    assert {c["id"] for c in payload} == {a.display_id}


async def test_filter_labels_is_not_present(client, seeded, db_session):
    """Mirrors ``NOT EXISTS (taggings...)`` — conversations with zero labels."""
    owner, _, _, _, ci_a, _, admin_h = seeded
    a = await _make_conv(db_session, contact_inbox=ci_a)
    b = await _make_conv(db_session, contact_inbox=ci_a)
    await update_labels(db_session, conversation=a, titles=["urgent"])

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/filter",
        json={
            "payload": [
                {
                    "attribute_key": "labels",
                    "filter_operator": "is_not_present",
                    "values": [],
                }
            ]
        },
        headers=admin_h,
    )
    assert resp.status_code == 200
    payload = resp.json()["payload"]
    assert {c["id"] for c in payload} == {b.display_id}


async def test_filter_or_combines_two_conditions(client, seeded, db_session):
    """``query_operator: OR`` joins the prior condition with the next.
    Two single-attribute filters with OR -> union of results."""
    owner, _, _, _, ci_a, _, admin_h = seeded
    a = await _make_conv(
        db_session, contact_inbox=ci_a, status=CONVERSATION_STATUS_RESOLVED
    )
    b = await _make_conv(
        db_session, contact_inbox=ci_a, priority=CONVERSATION_PRIORITY_URGENT
    )
    # Neither resolved nor urgent — must be excluded
    await _make_conv(db_session, contact_inbox=ci_a)

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/filter",
        json={
            "payload": [
                {
                    "attribute_key": "status",
                    "filter_operator": "equal_to",
                    "values": ["resolved"],
                    "query_operator": "OR",
                },
                {
                    "attribute_key": "priority",
                    "filter_operator": "equal_to",
                    "values": ["urgent"],
                    "query_operator": None,
                },
            ]
        },
        headers=admin_h,
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()["payload"]
    assert {c["id"] for c in payload} == {a.display_id, b.display_id}


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------
async def test_filter_rejects_missing_payload(client, seeded):
    owner, _, _, _, _, _, admin_h = seeded
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/filter",
        json={},
        headers=admin_h,
    )
    assert resp.status_code == 400
    assert "payload" in resp.json()["message"]


async def test_filter_rejects_unknown_attribute(client, seeded):
    owner, _, _, _, _, _, admin_h = seeded
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/filter",
        json={
            "payload": [
                {
                    "attribute_key": "rocket_engine_temperature",
                    "filter_operator": "equal_to",
                    "values": ["hot"],
                }
            ]
        },
        headers=admin_h,
    )
    assert resp.status_code == 400
    assert "Unsupported attribute" in resp.json()["message"]


async def test_filter_rejects_disallowed_operator(client, seeded):
    """``status`` only allows equal_to / not_equal_to per filter_keys.yml.
    ``contains`` should be rejected with the allowed-list in the message."""
    owner, _, _, _, _, _, admin_h = seeded
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/filter",
        json={
            "payload": [
                {
                    "attribute_key": "status",
                    "filter_operator": "contains",
                    "values": ["open"],
                }
            ]
        },
        headers=admin_h,
    )
    assert resp.status_code == 400
    assert "not allowed for status" in resp.json()["message"]


async def test_filter_rejects_invalid_query_operator(client, seeded):
    owner, _, _, _, _, _, admin_h = seeded
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/filter",
        json={
            "payload": [
                {
                    "attribute_key": "status",
                    "filter_operator": "equal_to",
                    "values": ["open"],
                    "query_operator": "XOR",
                }
            ]
        },
        headers=admin_h,
    )
    assert resp.status_code == 400
    assert "query_operator" in resp.json()["message"]


# ---------------------------------------------------------------------------
# Filtering by channel
# ---------------------------------------------------------------------------
@pytest.fixture
async def two_channels(db_session, seeded):
    """An Instagram inbox next to the fixture's API ones.

    The point of the attribute is telling channels apart, so the account
    needs more than one kind for the assertions to mean anything.
    """
    owner, _ia, _ib, contact, ci_a, _cib, admin_h = seeded
    ig = (
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="IG",
                channel_type="instagram",
                channel_params={
                    "instagram_id": "IG-FLT",
                    "access_token": "PAGE-TOKEN",
                },
            ),
        ).perform()
    ).inbox
    ci_ig = await ContactInboxBuilder(
        session=db_session, contact=contact, inbox=ig, source_id="IGSID-FLT"
    ).perform()
    from_api = await _make_conv(db_session, contact_inbox=ci_a)
    from_ig = await _make_conv(db_session, contact_inbox=ci_ig)
    return owner, admin_h, from_api, from_ig


async def _by_channel(client, owner, headers, value, op="equal_to"):
    return await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/filter",
        json={
            "payload": [
                {
                    "attribute_key": "channel",
                    "filter_operator": op,
                    "values": [value],
                    "query_operator": None,
                }
            ]
        },
        headers=headers,
    )


async def test_filter_channel_equal_to(client, two_channels):
    owner, admin_h, _from_api, from_ig = two_channels
    resp = await _by_channel(client, owner, admin_h, "instagram")
    assert resp.status_code == 200, resp.text
    assert {c["id"] for c in resp.json()["payload"]} == {from_ig.display_id}


async def test_filter_channel_not_equal_to(client, two_channels):
    owner, admin_h, from_api, from_ig = two_channels
    resp = await _by_channel(client, owner, admin_h, "instagram", "not_equal_to")
    ids = {c["id"] for c in resp.json()["payload"]}
    assert from_api.display_id in ids
    assert from_ig.display_id not in ids


async def test_filter_channel_accepts_the_stored_discriminator(
    client, two_channels
):
    """A hand-written API call should not have to know the short name."""
    owner, admin_h, _from_api, from_ig = two_channels
    resp = await _by_channel(client, owner, admin_h, "Channel::Instagram")
    assert {c["id"] for c in resp.json()["payload"]} == {from_ig.display_id}


async def test_filter_channel_is_case_insensitive(client, two_channels):
    owner, admin_h, _from_api, from_ig = two_channels
    resp = await _by_channel(client, owner, admin_h, "InStAgRaM")
    assert {c["id"] for c in resp.json()["payload"]} == {from_ig.display_id}


async def test_filter_channel_with_no_matches_is_empty_not_an_error(
    client, two_channels
):
    owner, admin_h, _from_api, _from_ig = two_channels
    resp = await _by_channel(client, owner, admin_h, "telegram")
    assert resp.status_code == 200
    assert resp.json()["payload"] == []


async def test_filter_channel_rejects_presence_operators(client, two_channels):
    """Every conversation has an inbox, so they would silently match all."""
    owner, admin_h, _from_api, _from_ig = two_channels
    resp = await _by_channel(client, owner, admin_h, "instagram", "is_present")
    assert resp.status_code == 400
