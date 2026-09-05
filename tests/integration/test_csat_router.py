"""Integration tests for CSAT — send-on-resolve + public submit +
dashboard listing + metrics.

Anchors:
  reference/chatwoot/app/services/message_templates/template/csat_survey.rb
  reference/chatwoot/app/controllers/public/api/v1/csat_survey_controller.rb
  reference/chatwoot/app/controllers/api/v1/accounts/csat_survey_responses_controller.rb
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import (
    CONTENT_TYPE_INPUT_CSAT,
    Conversation,
    Message,
)
from app.domains.conversations.service import (
    ConversationBuilderParams,
    create_conversation,
    toggle_status,
)
from app.domains.csat.models import CsatSurveyResponse
from app.domains.csat.service import (
    send_csat_message_on_resolve,
    submit_csat_response,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.main import app

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
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


async def _seed_admin(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@csat.example.com",
            account_name=f"CSAT{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    headers, new_tokens = create_new_auth_token(
        user_tokens=owner.user.tokens, uid=owner.user.uid
    )
    owner.user.tokens = new_tokens
    db_session.add(owner.user)
    await db_session.flush()
    return owner, headers.as_response_headers()


async def _seed_conversation(
    db_session,
    owner,
    *,
    csat_enabled: bool = True,
    csat_config: dict | None = None,
) -> Conversation:
    inbox = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="API",
            channel_type="api",
            channel_params={"webhook_url": "https://x.example.com"},
        ),
    ).perform()
    if csat_enabled:
        inbox.inbox.csat_survey_enabled = True
        if csat_config is not None:
            inbox.inbox.csat_config = csat_config
        db_session.add(inbox.inbox)
        await db_session.flush()
    contact = Contact(account_id=owner.account.id, name="Dora")
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session,
        contact=contact,
        inbox=inbox.inbox,
        source_id=f"src-{contact.id}",
    ).perform()
    return await create_conversation(
        db_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(),
    )


async def _input_csat_for(db_session, conv: Conversation) -> Message | None:
    return (
        await db_session.exec(
            select(Message).where(
                Message.conversation_id == conv.id,
                Message.content_type == CONTENT_TYPE_INPUT_CSAT,
            )
        )
    ).first()


# ---------------------------------------------------------------------------
# Send-on-resolve
# ---------------------------------------------------------------------------
async def test_resolve_inserts_input_csat_message_when_enabled(db_session):
    owner, _ = await _seed_admin(db_session, "-snd")
    conv = await _seed_conversation(db_session, owner)
    await toggle_status(db_session, conversation=conv, status="resolved")
    msg = await _input_csat_for(db_session, conv)
    assert msg is not None
    assert msg.content_type == CONTENT_TYPE_INPUT_CSAT
    assert (msg.content_attributes or {}).get("display_type") == "emoji"


async def test_resolve_skips_when_csat_disabled(db_session):
    owner, _ = await _seed_admin(db_session, "-off")
    conv = await _seed_conversation(db_session, owner, csat_enabled=False)
    await toggle_status(db_session, conversation=conv, status="resolved")
    msg = await _input_csat_for(db_session, conv)
    assert msg is None


async def test_resolve_only_inserts_once(db_session):
    """Re-resolving (open → resolved → open → resolved) should not
    create a second ``input_csat`` row."""
    owner, _ = await _seed_admin(db_session, "-once")
    conv = await _seed_conversation(db_session, owner)
    await toggle_status(db_session, conversation=conv, status="resolved")
    await toggle_status(db_session, conversation=conv, status="open")
    await toggle_status(db_session, conversation=conv, status="resolved")
    rows = list(
        (
            await db_session.exec(
                select(Message).where(
                    Message.conversation_id == conv.id,
                    Message.content_type == CONTENT_TYPE_INPUT_CSAT,
                )
            )
        ).all()
    )
    assert len(rows) == 1


async def test_resolve_uses_custom_message_from_config(db_session):
    owner, _ = await _seed_admin(db_session, "-cfg")
    conv = await _seed_conversation(
        db_session,
        owner,
        csat_config={"message": "How was your chat?", "display_type": "star"},
    )
    await send_csat_message_on_resolve(db_session, conversation=conv)
    msg = await _input_csat_for(db_session, conv)
    assert msg is not None
    assert msg.content == "How was your chat?"
    assert (msg.content_attributes or {}).get("display_type") == "star"


# ---------------------------------------------------------------------------
# Public submit
# ---------------------------------------------------------------------------
async def test_public_show_returns_message(client, db_session):
    owner, _ = await _seed_admin(db_session, "-psh")
    conv = await _seed_conversation(db_session, owner)
    await toggle_status(db_session, conversation=conv, status="resolved")
    resp = await client.get(f"/public/api/v1/csat_survey/{conv.uuid}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["content_type"] == "input_csat"


async def test_public_show_404_on_unknown_uuid(client):
    resp = await client.get(
        "/public/api/v1/csat_survey/00000000-0000-0000-0000-000000000000"
    )
    assert resp.status_code == 404


async def test_public_submit_creates_response_row(client, db_session):
    owner, _ = await _seed_admin(db_session, "-sub")
    conv = await _seed_conversation(db_session, owner)
    await toggle_status(db_session, conversation=conv, status="resolved")
    body = {
        "message": {
            "submitted_values": [
                {
                    "name": "rating",
                    "title": "Rate us",
                    "value": 5,
                    "csat_survey_response": {
                        "rating": 5,
                        "feedback_message": "Outstanding service",
                    },
                }
            ]
        }
    }
    resp = await client.put(
        f"/public/api/v1/csat_survey/{conv.uuid}", json=body
    )
    assert resp.status_code == 200, resp.text
    submitted = resp.json()["content_attributes"].get("submitted_values")
    assert submitted is not None

    row = (
        await db_session.exec(
            select(CsatSurveyResponse).where(
                CsatSurveyResponse.conversation_id == conv.id
            )
        )
    ).first()
    assert row is not None
    assert row.rating == 5
    assert row.feedback_message == "Outstanding service"


async def test_public_submit_rejects_invalid_rating(client, db_session):
    owner, _ = await _seed_admin(db_session, "-bad")
    conv = await _seed_conversation(db_session, owner)
    await toggle_status(db_session, conversation=conv, status="resolved")
    body = {
        "message": {
            "submitted_values": [
                {
                    "csat_survey_response": {
                        "rating": 99,
                        "feedback_message": "",
                    }
                }
            ]
        }
    }
    resp = await client.put(
        f"/public/api/v1/csat_survey/{conv.uuid}", json=body
    )
    assert resp.status_code == 422


async def test_public_submit_replaces_existing_response(client, db_session):
    owner, _ = await _seed_admin(db_session, "-rep")
    conv = await _seed_conversation(db_session, owner)
    await toggle_status(db_session, conversation=conv, status="resolved")
    base = {
        "message": {
            "submitted_values": [
                {"csat_survey_response": {"rating": 2, "feedback_message": "meh"}}
            ]
        }
    }
    upd = {
        "message": {
            "submitted_values": [
                {"csat_survey_response": {"rating": 5, "feedback_message": "fixed"}}
            ]
        }
    }
    r1 = await client.put(f"/public/api/v1/csat_survey/{conv.uuid}", json=base)
    assert r1.status_code == 200
    r2 = await client.put(f"/public/api/v1/csat_survey/{conv.uuid}", json=upd)
    assert r2.status_code == 200
    rows = list(
        (
            await db_session.exec(
                select(CsatSurveyResponse).where(
                    CsatSurveyResponse.conversation_id == conv.id
                )
            )
        ).all()
    )
    assert len(rows) == 1
    assert rows[0].rating == 5
    assert rows[0].feedback_message == "fixed"


async def test_public_submit_blocked_after_14_days(client, db_session):
    owner, _ = await _seed_admin(db_session, "-lock")
    conv = await _seed_conversation(db_session, owner)
    await toggle_status(db_session, conversation=conv, status="resolved")
    msg = await _input_csat_for(db_session, conv)
    assert msg is not None
    # Backdate the message past the 14-day window.
    msg.created_at = datetime.now(UTC) - timedelta(days=20)
    db_session.add(msg)
    await db_session.flush()

    body = {
        "message": {
            "submitted_values": [
                {"csat_survey_response": {"rating": 4, "feedback_message": "late"}}
            ]
        }
    }
    resp = await client.put(
        f"/public/api/v1/csat_survey/{conv.uuid}", json=body
    )
    assert resp.status_code == 422
    assert "14 days" in resp.json()["error"]


# ---------------------------------------------------------------------------
# Dashboard listing + metrics
# ---------------------------------------------------------------------------
async def test_dashboard_index_returns_array(client, db_session):
    owner, headers = await _seed_admin(db_session, "-ix")
    conv = await _seed_conversation(db_session, owner)
    await toggle_status(db_session, conversation=conv, status="resolved")
    await submit_csat_response(
        db_session, conversation=conv, rating=4, feedback_message="ok"
    )
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/csat_survey_responses",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]["rating"] == 4


async def test_dashboard_index_filters_by_rating(client, db_session):
    owner, headers = await _seed_admin(db_session, "-fr")
    # Two conversations, two ratings.
    for score in (2, 5):
        conv = await _seed_conversation(db_session, owner)
        await toggle_status(db_session, conversation=conv, status="resolved")
        await submit_csat_response(
            db_session, conversation=conv, rating=score
        )
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/csat_survey_responses?rating=5",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["rating"] == 5


async def test_dashboard_metrics_shape(client, db_session):
    owner, headers = await _seed_admin(db_session, "-mt")
    # Two responses + a third resolved conversation with NO response →
    # total_sent_messages_count = 3, total_count = 2.
    for score in [3, 4]:
        conv = await _seed_conversation(db_session, owner)
        await toggle_status(db_session, conversation=conv, status="resolved")
        await submit_csat_response(
            db_session, conversation=conv, rating=score
        )
    no_response = await _seed_conversation(db_session, owner)
    await toggle_status(
        db_session, conversation=no_response, status="resolved"
    )
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/csat_survey_responses/metrics",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_count"] == 2
    assert body["total_sent_messages_count"] == 3
    # ratings_count keys come back as ints serialized as strings by FastAPI's
    # json encoder for dict-int keys; tolerate both representations.
    ratings = {int(k): v for k, v in body["ratings_count"].items()}
    assert ratings == {3: 1, 4: 1}


async def test_dashboard_index_isolates_per_account(client, db_session):
    owner_a, headers_a = await _seed_admin(db_session, "-ax")
    owner_b, _ = await _seed_admin(db_session, "-bx")
    conv_b = await _seed_conversation(db_session, owner_b)
    await toggle_status(db_session, conversation=conv_b, status="resolved")
    await submit_csat_response(db_session, conversation=conv_b, rating=5)
    resp = await client.get(
        f"/api/v1/accounts/{owner_a.account.id}/csat_survey_responses",
        headers=headers_a,
    )
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# What the listing costs
# ---------------------------------------------------------------------------
class _QueryCounter:
    def __init__(self) -> None:
        self.total = 0

    def __call__(self, conn, cursor, statement, params, context, executemany):
        self.total += 1


@pytest.fixture
def query_counter(db_session):
    from sqlalchemy import event

    bind = db_session.get_bind()
    target = getattr(bind, "sync_engine", bind)
    counter = _QueryCounter()
    event.listen(target, "before_cursor_execute", counter)
    try:
        yield counter
    finally:
        event.remove(target, "before_cursor_execute", counter)


async def test_the_listing_does_not_query_per_row(
    client, db_session, query_counter
):
    """It used to: contact, conversation, then a user and an account_user
    for each of the two agent slots — up to six queries per row, so a
    page of 12 cost about seventy.

    Asserted as "the same for 12 rows as for 2" rather than a fixed
    ceiling: a per-row query is the failure, and a count that grows with
    the page is what proves it, independent of how much the surrounding
    endpoint costs.
    """
    owner, headers = await _seed_admin(db_session, "-nplus1")

    async def make(n: int) -> None:
        # One survey per conversation — the table enforces it, which is
        # also why each response brings its own contact to look up.
        from app.domains.conversations.models import (
            MESSAGE_TYPE_OUTGOING,
            Message,
        )

        for i in range(n):
            conv = await _seed_conversation(db_session, owner)
            msg = Message(
                account_id=owner.account.id,
                inbox_id=conv.inbox_id,
                conversation_id=conv.id,
                message_type=MESSAGE_TYPE_OUTGOING,
                content="¿Cómo te fue?",
            )
            db_session.add(msg)
            await db_session.flush()
            db_session.add(
                CsatSurveyResponse(
                    account_id=owner.account.id,
                    conversation_id=conv.id,
                    contact_id=conv.contact_id,
                    message_id=msg.id,
                    rating=(i % 5) + 1,
                    assigned_agent_id=owner.user.id,
                )
            )
        await db_session.flush()

    async def cost() -> int:
        db_session.expunge_all()
        query_counter.total = 0
        resp = await client.get(
            f"/api/v1/accounts/{owner.account.id}/csat_survey_responses",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        return query_counter.total

    await make(2)
    con_pocas = await cost()
    await make(10)
    con_muchas = await cost()

    print(f"\n  2 respuestas: {con_pocas} consultas | 12: {con_muchas}")
    assert con_muchas == con_pocas, (
        f"2 respuestas costaron {con_pocas} consultas y 12 costaron "
        f"{con_muchas}: algo se consulta por fila."
    )
