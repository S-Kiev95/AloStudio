"""Outbound webhooks for records: contacts (Chatwoot parity), and
AloStudio's own appointment and publication events.

Record events go out after the commit (like Rails' ``after_*_commit``), so
every test commits and then waits for the post-commit enqueues.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.core.models_registry import import_all_models
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.appointments import service as appointments
from app.domains.appointments.importer import import_postiz_crm
from app.domains.contacts.service import (
    ContactIdentifyAction,
    create_contact,
    update_contact,
)
from app.domains.conversations.service import (
    mute_conversation_with_activity,
    unmute_conversation_with_activity,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.publishing import service as publishing
from app.domains.publishing.adapters import PublishResult
from app.domains.publishing.adapters.facebook_page import FacebookPageAdapter
from app.domains.webhooks import listener as webhook_listener
from app.domains.webhooks.service import create_webhook
from app.domains.whatsapp import incoming_cloud
from tests.integration._publishing import channel_id_of

import_all_models()

pytestmark = pytest.mark.integration


@pytest.fixture
def deliveries(monkeypatch) -> list[dict[str, Any]]:
    """Capture what would be POSTed instead of enqueueing it."""
    sent: list[dict[str, Any]] = []

    async def _capture(**kwargs):
        json.dumps(kwargs["body"])  # must be sendable as-is
        sent.append(kwargs)

    monkeypatch.setattr(webhook_listener, "enqueue_delivery", _capture)
    return sent


async def _commit(db_session) -> None:
    await db_session.commit()
    await webhook_listener.wait_for_pending_deliveries()


async def _account(db_session, suffix: str, *, events: list[str]):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@hooks.example.com",
            account_name=f"HOOKS{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    await create_webhook(
        db_session,
        account_id=owner.account.id,
        payload={"url": f"https://hooks.example.com/{suffix}", "subscriptions": events},
    )
    return owner


def _events(sent: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    return [d["body"] for d in sent if d["event_name"] == name]


async def test_contact_created_from_the_api_and_from_a_channel(db_session, deliveries):
    owner = await _account(db_session, "-cc", events=["contact_created"])

    contact = await create_contact(
        db_session,
        account_id=owner.account.id,
        payload={"name": "Ana", "email": "ana@example.com"},
    )
    from_whatsapp = await incoming_cloud._find_or_create_contact(
        db_session,
        account_id=owner.account.id,
        phone_number="+59899111222",
        name="Beto",
    )
    assert deliveries == []  # nothing before the commit
    await _commit(db_session)

    bodies = _events(deliveries, "contact_created")
    assert [b["id"] for b in bodies] == [contact.id, from_whatsapp.id]
    first = bodies[0]
    assert first["event"] == "contact_created"
    assert first["email"] == "ana@example.com"
    assert first["account"] == {"id": owner.account.id, "name": owner.account.name}
    assert first["event_id"]
    assert "changed_attributes" not in first


async def test_rolled_back_contacts_are_never_announced(db_session, deliveries):
    owner = await _account(db_session, "-rb", events=["contact_created"])
    await _commit(db_session)

    # A savepoint that fails (an inbound change that blew up halfway).
    with pytest.raises(RuntimeError):
        async with db_session.begin_nested():
            await create_contact(
                db_session, account_id=owner.account.id, payload={"name": "Fantasma"}
            )
            raise RuntimeError("boom")
    kept = await create_contact(
        db_session, account_id=owner.account.id, payload={"name": "Real"}
    )
    kept_id = kept.id
    await _commit(db_session)

    # A whole transaction that rolls back.
    await create_contact(
        db_session, account_id=owner.account.id, payload={"name": "Tampoco"}
    )
    await db_session.rollback()
    await webhook_listener.wait_for_pending_deliveries()

    assert [b["id"] for b in _events(deliveries, "contact_created")] == [kept_id]


async def test_contact_updated_carries_changes_and_skips_no_ops(db_session, deliveries):
    owner = await _account(db_session, "-cu", events=["contact_updated"])
    contact = await create_contact(
        db_session, account_id=owner.account.id, payload={"name": "Ana"}
    )

    await update_contact(db_session, contact=contact, payload={"name": "Ana María"})
    await update_contact(db_session, contact=contact, payload={"name": "Ana María"})
    await _commit(db_session)

    (body,) = _events(deliveries, "contact_updated")
    assert body["name"] == "Ana María"
    assert body["changed_attributes"] == [
        {"name": {"previous_value": "Ana", "current_value": "Ana María"}}
    ]


async def test_other_contact_changes_are_announced(db_session, deliveries):
    """Identify (widget pre-chat), mute/unmute and the WhatsApp profile
    name all change the contact, so Rails sends ``contact_updated``."""
    owner = await _account(db_session, "-other", events=["contact_updated"])
    contact = await create_contact(
        db_session, account_id=owner.account.id, payload={"name": "Visitante"}
    )
    await ContactIdentifyAction(
        session=db_session,
        contact=contact,
        params={"email": "visita@example.com"},
    ).perform()
    numbered = await incoming_cloud._find_or_create_contact(
        db_session,
        account_id=owner.account.id,
        phone_number="+59899000111",
        name=None,
    )
    await incoming_cloud._find_or_create_contact(
        db_session,
        account_id=owner.account.id,
        phone_number="+59899000111",
        name="Carla",
    )
    await _commit(db_session)

    changes = [
        (b["id"], next(iter(b["changed_attributes"][0])))
        for b in _events(deliveries, "contact_updated")
    ]
    assert (contact.id, "email") in changes
    assert (numbered.id, "name") in changes


async def test_mute_and_unmute_announce_blocked(db_session, deliveries, monkeypatch):
    owner = await _account(db_session, "-mute", events=["contact_updated"])
    contact = await create_contact(
        db_session, account_id=owner.account.id, payload={"name": "Ruidoso"}
    )

    class _Conversation:
        pass

    conversation = _Conversation()
    conversation.contact = contact

    async def _noop(*args, **kwargs):
        return None

    from app.domains.conversations import service as conversations

    monkeypatch.setattr(conversations, "toggle_status", _noop)
    monkeypatch.setattr(conversations, "create_activity_message", _noop)
    monkeypatch.setattr(conversations, "_current_user_name", lambda: "Agente")

    await mute_conversation_with_activity(db_session, conversation=conversation)
    await unmute_conversation_with_activity(db_session, conversation=conversation)
    await _commit(db_session)

    assert [
        b["changed_attributes"] for b in _events(deliveries, "contact_updated")
    ] == [
        [{"blocked": {"previous_value": False, "current_value": True}}],
        [{"blocked": {"previous_value": True, "current_value": False}}],
    ]


async def test_only_subscribed_webhooks_receive(db_session, deliveries):
    owner = await _account(db_session, "-sub", events=["message_created"])

    await create_contact(db_session, account_id=owner.account.id, payload={"name": "X"})
    await _commit(db_session)

    assert deliveries == []


async def test_appointment_events(db_session, deliveries):
    owner = await _account(
        db_session, "-ap", events=["appointment_created", "appointment_updated"]
    )
    contact = await create_contact(
        db_session, account_id=owner.account.id, payload={"name": "Cliente"}
    )
    starts = datetime(2026, 11, 5, 14, 0, tzinfo=UTC)

    appointment = await appointments.create_appointment(
        db_session,
        account_id=owner.account.id,
        payload={"contact_id": contact.id, "title": "Turno", "starts_at": starts},
    )
    await appointments.update_appointment(
        db_session, appointment=appointment, payload={"status": "confirmed"}
    )
    await _commit(db_session)

    (created,) = _events(deliveries, "appointment_created")
    assert created["id"] == appointment.id
    assert created["contact_id"] == contact.id
    assert created["starts_at"] == starts.isoformat()
    assert created["status"] == "scheduled"
    (updated,) = _events(deliveries, "appointment_updated")
    assert updated["status"] == "confirmed"
    assert updated["changed_attributes"] == [
        {"status": {"previous_value": "scheduled", "current_value": "confirmed"}}
    ]


async def test_bulk_import_announces_nothing(db_session, deliveries):
    owner = await _account(
        db_session, "-imp", events=["contact_created", "appointment_created"]
    )

    await import_postiz_crm(
        db_session,
        account_id=owner.account.id,
        data={
            "customers": [{"id": "c1", "name": "Importada", "email": "imp@example.com"}],
            "products": [],
            "appointments": [
                {
                    "id": "a1",
                    "customerId": "c1",
                    "title": "Turno importado",
                    "startDate": "2026-11-05T14:00:00.000Z",
                    "status": "SCHEDULED",
                }
            ],
        },
    )
    await _commit(db_session)

    assert deliveries == []


async def test_publication_completed_reports_each_channel(db_session, deliveries, monkeypatch):
    owner = await _account(db_session, "-pub", events=["publication_completed"])
    page = (
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="Pagina",
                channel_type="facebook",
                channel_params={"page_id": "PHOOK", "page_access_token": "t"},
            ),
        ).perform()
    ).inbox
    publication = await publishing.create_publication(
        db_session,
        account_id=owner.account.id,
        payload={
            "content": "Hola",
            "scheduled_for": datetime.now(UTC) + timedelta(hours=1),
            "targets": [{"channel_id": await channel_id_of(db_session, page)}],
        },
    )
    publication.scheduled_for = datetime.now(UTC) - timedelta(minutes=1)
    db_session.add(publication)
    await db_session.flush()
    assert await publishing.start_publishing(db_session, publication_id=publication.id)

    async def _publish(self, session, publication, target):
        return PublishResult(ok=True, external_id="PHOOK_1", permalink="https://fb/1")

    monkeypatch.setattr(FacebookPageAdapter, "publish", _publish)

    await publishing.publish_pending_targets(db_session, publication_id=publication.id)
    await webhook_listener.wait_for_pending_deliveries()

    (body,) = _events(deliveries, "publication_completed")
    assert body["id"] == publication.id
    assert body["state"] == "published"
    assert body["published_at"] is not None
    (target,) = body["targets"]
    assert target["channel_id"] == await channel_id_of(db_session, page)
    assert target["inbox_id"] == page.id
    assert target["network"] == "facebook_page"
    assert target["state"] == "published"
    assert target["permalink"] == "https://fb/1"
