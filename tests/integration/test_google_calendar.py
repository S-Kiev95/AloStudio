"""Google Calendar (F17): each agent's appointments and tasks in their own
calendar. Google is mocked with respx."""

from __future__ import annotations

import base64
import json
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.config import get_settings
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.appointments.models import Appointment
from app.domains.contacts.models import Contact
from app.domains.crm.models import CrmActivity
from app.domains.google_calendar import client as gclient
from app.domains.google_calendar import service
from app.domains.google_calendar.models import GoogleCalendarEvent, GoogleCalendarLink
from app.main import app

pytestmark = pytest.mark.integration


class FakeGoogle:
    """Token endpoint and the primary calendar's events."""

    def __init__(self) -> None:
        self.events: dict[str, dict[str, Any]] = {}
        self.calls: list[tuple[str, str]] = []
        self.revoked_grant = False
        self._next = 0

    def token(self, request: httpx.Request) -> httpx.Response:
        form = parse_qs(request.content.decode())
        if form["grant_type"] == ["authorization_code"]:
            claims = base64.urlsafe_b64encode(json.dumps({"email": "sofia@gmail.com"}).encode())
            id_token = f"x.{claims.decode().rstrip('=')}.y"
            return httpx.Response(
                200, json={"access_token": "a", "refresh_token": "1//refresh", "id_token": id_token}
            )
        if self.revoked_grant:
            return httpx.Response(400, json={"error": "invalid_grant"})
        return httpx.Response(200, json={"access_token": "a", "expires_in": 3600})

    def events_api(self, request: httpx.Request) -> httpx.Response:
        event_id = request.url.path.rsplit("/", 1)[-1]
        self.calls.append((request.method, event_id if event_id != "events" else ""))
        if request.method == "POST":
            self._next += 1
            new_id = f"ev{self._next}"
            self.events[new_id] = json.loads(request.content)
            return httpx.Response(200, json={"id": new_id})
        if request.method == "PUT":
            if event_id not in self.events:
                return httpx.Response(404, json={"error": {"message": "Not Found"}})
            self.events[event_id] = json.loads(request.content)
            return httpx.Response(200, json={"id": event_id})
        self.events.pop(event_id, None)
        return httpx.Response(204)


@pytest.fixture
def google(monkeypatch) -> Iterator[FakeGoogle]:
    settings = get_settings()
    monkeypatch.setattr(settings, "google_client_id", "client-id")
    monkeypatch.setattr(settings, "google_client_secret", "client-secret")
    fake = FakeGoogle()
    with respx.mock(assert_all_called=False) as mock:
        mock.post(gclient.TOKEN_URL).mock(side_effect=fake.token)
        mock.post(gclient.REVOKE_URL).mock(return_value=httpx.Response(200))
        mock.route(url__startswith=gclient.EVENTS_URL).mock(side_effect=fake.events_api)
        yield fake


@pytest.fixture
async def client(db_session) -> AsyncIterator[AsyncClient]:
    async def _override() -> AsyncIterator:
        yield db_session

    app.dependency_overrides[get_session] = _override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_session, None)


async def _headers(db_session, user) -> dict[str, str]:
    headers, tokens = create_new_auth_token(user_tokens=user.tokens, uid=user.uid)
    user.tokens = tokens
    db_session.add(user)
    await db_session.flush()
    return headers.as_response_headers()


@pytest.fixture
async def seeded(db_session):
    built = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="sofia@gcal.example.com",
            account_name="Instituto",
            user_full_name="Sofía",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    other = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="pablo@gcal.example.com",
            account_name="Otra",
            user_full_name="Pablo",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    contact = Contact(account_id=built.account.id, name="Lucía Pereira")
    db_session.add(contact)
    await db_session.flush()
    return {"account": built.account, "user": built.user, "other": other.user, "contact": contact}


async def _connect(client, db_session, user) -> None:
    headers = await _headers(db_session, user)
    url = (
        await client.get("/api/v1/profile/google_calendar/authorize_url", headers=headers)
    ).json()["url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    done = await client.post(
        "/api/v1/profile/google_calendar", json={"code": "4/abc", "state": state}, headers=headers
    )
    assert done.status_code == 200, done.text


async def test_connecting_keeps_the_token_encrypted(client, db_session, seeded, google):
    user = seeded["user"]
    headers = await _headers(db_session, user)
    shown = (await client.get("/api/v1/profile/google_calendar", headers=headers)).json()
    assert shown == {
        "available": True,
        "connected": False,
        "email": None,
        "last_synced_at": None,
        "problem": None,
    }
    url = (
        await client.get("/api/v1/profile/google_calendar/authorize_url", headers=headers)
    ).json()["url"]
    query = parse_qs(urlparse(url).query)
    assert query["scope"] == [gclient.SCOPES]
    assert query["access_type"] == ["offline"]
    assert query["redirect_uri"][0].endswith("/google-calendar/callback")

    # A state made for someone else is refused.
    other_headers = await _headers(db_session, seeded["other"])
    refused = await client.post(
        "/api/v1/profile/google_calendar",
        json={"code": "4/abc", "state": query["state"][0]},
        headers=other_headers,
    )
    assert refused.json()["code"] == "google_calendar.state"

    await _connect(client, db_session, user)
    link = await db_session.get(GoogleCalendarLink, user.id)
    assert link.google_email == "sofia@gmail.com"
    assert "1//refresh" not in link.refresh_token_encrypted
    shown = (await client.get("/api/v1/profile/google_calendar", headers=headers)).json()
    assert shown["connected"] is True and shown["email"] == "sofia@gmail.com"


async def test_off_without_googles_credentials(client, db_session, seeded, monkeypatch):
    monkeypatch.setattr(get_settings(), "google_client_id", "")
    headers = await _headers(db_session, seeded["user"])
    assert (await client.get("/api/v1/profile/google_calendar", headers=headers)).json()[
        "available"
    ] is False
    refused = await client.get("/api/v1/profile/google_calendar/authorize_url", headers=headers)
    assert refused.json()["code"] == "google_calendar.unavailable"


async def test_the_agenda_goes_to_the_calendar_and_follows_changes(
    client, db_session, seeded, google
):
    user, account, contact = seeded["user"], seeded["account"], seeded["contact"]
    await _connect(client, db_session, user)
    soon = datetime.now(UTC) + timedelta(days=2)
    visit = Appointment(
        account_id=account.id,
        contact_id=contact.id,
        title="Entrevista",
        starts_at=soon,
        ends_at=soon + timedelta(hours=1),
        created_by_id=user.id,
    )
    cancelled = Appointment(
        account_id=account.id,
        contact_id=contact.id,
        title="Cancelada",
        starts_at=soon,
        status="cancelled",
        created_by_id=user.id,
    )
    someone_elses = Appointment(
        account_id=account.id,
        contact_id=contact.id,
        title="De Pablo",
        starts_at=soon,
        created_by_id=seeded["other"].id,
    )
    call_back = CrmActivity(
        account_id=account.id,
        kind="call",
        title="Llamar por la beca",
        due_at=soon + timedelta(hours=3),
        owner_id=user.id,
        contact_id=contact.id,
    )
    db_session.add_all([visit, cancelled, someone_elses, call_back])
    await db_session.flush()

    assert await service.sync_all(db_session) == 2
    summaries = sorted(e["summary"] for e in google.events.values())
    assert summaries == ["Entrevista · Lucía Pereira", "Llamar por la beca · Lucía Pereira"]
    interview = next(e for e in google.events.values() if e["summary"].startswith("Entrevista"))
    assert interview["end"]["dateTime"] == (soon + timedelta(hours=1)).astimezone(UTC).isoformat()
    assert f"/accounts/{account.id}/contacts/{contact.id}" in interview["description"]

    google.calls.clear()
    assert await service.sync_all(db_session) == 0, "nothing changed, nothing sent"
    assert google.calls == []

    visit.title = "Entrevista con la directora"
    call_back.done_at = datetime.now(UTC)
    db_session.add_all([visit, call_back])
    await db_session.flush()
    assert await service.sync_all(db_session) == 2
    assert sorted(m for m, _ in google.calls) == ["DELETE", "PUT"]
    assert [e["summary"] for e in google.events.values()] == [
        "Entrevista con la directora · Lucía Pereira"
    ]

    # Deleted on Google's side: made again on the next change.
    google.events.clear()
    visit.title = "Entrevista (cambio de hora)"
    db_session.add(visit)
    await db_session.flush()
    assert await service.sync_all(db_session) == 1
    assert len(google.events) == 1


async def test_a_revoked_access_stops_trying(client, db_session, seeded, google):
    user = seeded["user"]
    await _connect(client, db_session, user)
    google.revoked_grant = True
    assert await service.sync_all(db_session) == 0
    link = await db_session.get(GoogleCalendarLink, user.id)
    assert link.last_error == "revoked"
    headers = await _headers(db_session, user)
    shown = (await client.get("/api/v1/profile/google_calendar", headers=headers)).json()
    assert shown["problem"] == "revoked"


async def test_disconnecting_takes_our_events_off(client, db_session, seeded, google):
    user, account, contact = seeded["user"], seeded["account"], seeded["contact"]
    await _connect(client, db_session, user)
    db_session.add(
        Appointment(
            account_id=account.id,
            contact_id=contact.id,
            title="Entrevista",
            starts_at=datetime.now(UTC) + timedelta(days=1),
            created_by_id=user.id,
        )
    )
    await db_session.flush()
    await service.sync_all(db_session)
    assert len(google.events) == 1

    headers = await _headers(db_session, user)
    gone = await client.delete("/api/v1/profile/google_calendar", headers=headers)
    assert gone.json()["connected"] is False
    assert google.events == {}
    rows = (
        await db_session.exec(
            select(GoogleCalendarEvent).where(GoogleCalendarEvent.user_id == user.id)
        )
    ).all()
    assert rows == []
