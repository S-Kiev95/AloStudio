"""Integration tests for v2.9 webhook retries + dead-letter.

Three layers:

  1. ``deliver_webhook_now`` — pure delivery logic, no ARQ, no DB.
     Tests poke this directly with respx mocks and assert the
     ``DeliveryOutcome`` returned.
  2. ``deliver_webhook_task`` — ARQ wrapper. Tests stub
     ``ctx['job_try']`` to walk the retry ladder + assert the
     dead-letter row lands on the last attempt.
  3. End-to-end via the listeners — covered by the existing
     ``test_agent_bot_listener.py`` + ``test_webhooks_router.py``
     because the inline fallback in
     :func:`app.workers.deliver_webhook.enqueue_delivery` hits the
     same code path when no ARQ pool is reachable (the test env).

Anchors:
  app/workers/deliver_webhook.py
"""

from __future__ import annotations

import httpx
import pytest
import respx
from sqlmodel import select

from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.agent_bots.models import AgentBot, AgentBotInbox
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.service import (
    ConversationBuilderParams,
    MessageBuilderParams,
    create_conversation,
    create_message,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.domains.webhooks.models import (
    RECEIVER_KIND_AGENT_BOT,
    RECEIVER_KIND_WEBHOOK,
    WebhookDeadLetter,
)
from app.workers.deliver_webhook import (
    BACKOFF_SECONDS,
    MAX_ATTEMPTS,
    DeliveryOutcome,
    deliver_webhook_now,
    deliver_webhook_task,
)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Layer 1: deliver_webhook_now — pure logic
# ---------------------------------------------------------------------------
@respx.mock
async def test_deliver_now_returns_ok_on_2xx():
    respx.post("https://hook.example.com/ok").mock(
        return_value=httpx.Response(200)
    )
    outcome = await deliver_webhook_now(
        url="https://hook.example.com/ok",
        body={"event": "ping", "event_id": "abc"},
        secret="s",
        attempt=1,
    )
    assert outcome.kind == "ok"
    assert outcome.status_code == 200
    assert outcome.next_backoff_seconds is None


@respx.mock
async def test_deliver_now_returns_retry_with_backoff_on_5xx_early_attempts():
    respx.post("https://hook.example.com/500").mock(
        return_value=httpx.Response(500, text="boom")
    )
    # Walk the schedule: 1→5s, 2→30s, 3→300s.
    for attempt, expected_defer in [(1, 5), (2, 30), (3, 5 * 60)]:
        outcome = await deliver_webhook_now(
            url="https://hook.example.com/500",
            body={"event": "ping"},
            secret="s",
            attempt=attempt,
        )
        assert outcome.kind == "retry", attempt
        assert outcome.next_backoff_seconds == expected_defer, attempt
        assert outcome.status_code == 500


@respx.mock
async def test_deliver_now_returns_dead_letter_on_final_attempt():
    """``attempt=MAX_ATTEMPTS`` (= 4 today) exhausts the schedule —
    next outcome must be ``dead_letter`` instead of ``retry``."""
    respx.post("https://hook.example.com/dead").mock(
        return_value=httpx.Response(500, text="boom forever")
    )
    outcome = await deliver_webhook_now(
        url="https://hook.example.com/dead",
        body={"event": "ping"},
        secret="s",
        attempt=MAX_ATTEMPTS,
    )
    assert outcome.kind == "dead_letter"
    assert outcome.status_code == 500
    assert outcome.next_backoff_seconds is None


@respx.mock
async def test_deliver_now_transport_error_treated_as_retry_then_dead_letter():
    """Connect timeouts / DNS errors go down the same retry+dead-letter
    path as 5xx — the receiver is unreachable, attempt budget applies."""
    respx.post("https://hook.example.com/dns").mock(
        side_effect=httpx.ConnectError("dns")
    )
    early = await deliver_webhook_now(
        url="https://hook.example.com/dns",
        body={"event": "ping"},
        secret="s",
        attempt=2,
    )
    assert early.kind == "retry"
    assert early.next_backoff_seconds == 30

    late = await deliver_webhook_now(
        url="https://hook.example.com/dns",
        body={"event": "ping"},
        secret="s",
        attempt=MAX_ATTEMPTS,
    )
    assert late.kind == "dead_letter"
    assert late.status_code is None  # transport error — no HTTP response
    assert late.error  # carries the exception summary


def test_backoff_schedule_matches_chatwoot_webhook_job():
    """5s / 30s / 5min / 30min — same as Chatwoot's ``retry_on``.
    Locking the literal table down so a future tweak is intentional."""
    assert BACKOFF_SECONDS[1] == 5
    assert BACKOFF_SECONDS[2] == 30
    assert BACKOFF_SECONDS[3] == 5 * 60
    assert BACKOFF_SECONDS[4] == 30 * 60
    assert MAX_ATTEMPTS == 5


@respx.mock
async def test_retry_schedule_is_actually_applied_at_runtime():
    """Behavioural lock (not just the dict literal): walk a forever-500
    receiver through every attempt and assert the *returned* backoffs are
    5s / 30s / 5min / 30min — i.e. all four retries fire, including the
    30-min tier — then attempt 5 dead-letters. This is the test the
    original suite lacked: it asserted the schedule dict existed but never
    that 1800s was ever returned, which masked an off-by-one (MAX_ATTEMPTS
    was 4, so the 30-min tier was dead code)."""
    respx.post("https://hook.example.com/sched").mock(
        return_value=httpx.Response(500, text="forever")
    )
    seen_backoffs: list[int | None] = []
    kinds: list[str] = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        o = await deliver_webhook_now(
            url="https://hook.example.com/sched",
            body={"event": "ping"},
            secret="s",
            attempt=attempt,
        )
        kinds.append(o.kind)
        seen_backoffs.append(o.next_backoff_seconds)

    # Four retries with the documented waits, then quarantine.
    assert kinds == ["retry", "retry", "retry", "retry", "dead_letter"]
    assert seen_backoffs == [5, 30, 300, 1800, None]
    # The 30-min tier is genuinely exercised (regression guard for the
    # off-by-one).
    assert 1800 in seen_backoffs


# ---------------------------------------------------------------------------
# Layer 2: ARQ wrapper — exhausted task writes a dead-letter row
# ---------------------------------------------------------------------------
@respx.mock
async def test_arq_task_writes_dead_letter_row_when_exhausted(db_session):
    """Simulate the last retry firing: 500 + ``job_try=MAX_ATTEMPTS`` →
    the task body writes the dead-letter row + returns normally."""
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="dl-owner@v29.example.com",
            account_name="DL Acct",
            user_full_name="DL Admin",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    url = "https://hook.example.com/dead-task"
    respx.post(url).mock(return_value=httpx.Response(500, text="hard fail"))

    # The task body opens its own session from ``ctx['engine']``.
    # Hand it the integration test's engine so writes land in the same
    # transaction db_session can see.
    ctx = {
        "job_try": MAX_ATTEMPTS,
        "engine": db_session.bind,
    }
    result = await deliver_webhook_task(
        ctx,
        account_id=owner.account.id,
        receiver_kind=RECEIVER_KIND_WEBHOOK,
        receiver_id=42,
        url=url,
        event_name="message_created",
        body={"event": "message_created", "event_id": "evt-1", "content": "x"},
        secret="s",
    )
    assert result["dead_letter"] is True
    assert result["status_code"] == 500
    assert result["attempts"] == MAX_ATTEMPTS

    # The dead-letter row exists. Using a fresh nested session because
    # the ARQ task writes via its own session/connection and the
    # outer db_session won't see uncommitted rows from another conn —
    # except we pass the bind and commit() inside the task body, so
    # a re-SELECT from db_session sees it.
    rows = list(
        (
            await db_session.exec(
                select(WebhookDeadLetter).where(
                    WebhookDeadLetter.account_id == owner.account.id
                )
            )
        ).all()
    )
    assert len(rows) == 1
    dl = rows[0]
    assert dl.receiver_kind == RECEIVER_KIND_WEBHOOK
    assert dl.receiver_id == 42
    assert dl.url == url
    assert dl.event_name == "message_created"
    assert dl.event_id == "evt-1"
    assert dl.last_status_code == 500
    assert dl.attempts == MAX_ATTEMPTS
    assert dl.body["content"] == "x"


@respx.mock
async def test_arq_task_raises_retry_on_transient_failure(db_session):
    """A 500 on an early attempt → ARQ ``Retry`` exception with the
    right ``defer`` value. We catch the exception type explicitly to
    confirm we're not silently giving up early."""
    from arq.worker import Retry

    url = "https://hook.example.com/transient"
    respx.post(url).mock(return_value=httpx.Response(503, text="overload"))

    ctx = {"job_try": 2}
    with pytest.raises(Retry) as info:
        await deliver_webhook_task(
            ctx,
            account_id=1,
            receiver_kind=RECEIVER_KIND_AGENT_BOT,
            receiver_id=7,
            url=url,
            event_name="conversation_updated",
            body={"event": "conversation_updated", "event_id": "evt-2"},
            secret="s",
        )
    # ``Retry.defer_score`` carries the deferral in milliseconds in
    # arq 0.26+ — convert back to seconds to compare with the schedule.
    defer_ms = info.value.defer_score
    assert defer_ms == BACKOFF_SECONDS[2] * 1000  # 30s → 30000ms


# ---------------------------------------------------------------------------
# Layer 3: end-to-end through the listener (inline fallback path)
# ---------------------------------------------------------------------------
async def _seed_bot_attached(db_session, owner, *, outgoing_url, secret="s"):
    inbox = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="API",
            channel_type="api",
            channel_params={"webhook_url": "https://x.example.com"},
        ),
    ).perform()
    contact = Contact(account_id=owner.account.id, name="X")
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session,
        contact=contact,
        inbox=inbox.inbox,
        source_id=f"src-{contact.id}",
    ).perform()
    bot = AgentBot(
        account_id=owner.account.id,
        name="Bot",
        outgoing_url=outgoing_url,
        secret=secret,
    )
    db_session.add(bot)
    await db_session.flush()
    await db_session.refresh(bot)
    db_session.add(
        AgentBotInbox(
            account_id=owner.account.id,
            inbox_id=inbox.inbox.id,
            agent_bot_id=bot.id,
            status=0,
        )
    )
    await db_session.flush()
    conv = await create_conversation(
        db_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(),
    )
    return bot, conv


@respx.mock
async def test_listener_inline_fallback_writes_dead_letter_on_5xx(db_session):
    """End-to-end: a bot receiver that 500s through the listener's
    inline fallback (no ARQ in tests) lands a dead-letter row."""
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="lst-owner@v29.example.com",
            account_name="Listener DL",
            user_full_name="LDL Admin",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    bot, conv = await _seed_bot_attached(
        db_session, owner, outgoing_url="https://bot.example.com/lst-500"
    )
    respx.post("https://bot.example.com/lst-500").mock(
        return_value=httpx.Response(500, text="nope")
    )
    await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(
            content="trigger", message_type="incoming"
        ),
        user_id=None,
    )

    rows = list(
        (
            await db_session.exec(
                select(WebhookDeadLetter).where(
                    WebhookDeadLetter.receiver_kind == RECEIVER_KIND_AGENT_BOT,
                    WebhookDeadLetter.receiver_id == bot.id,
                )
            )
        ).all()
    )
    assert len(rows) == 1
    assert rows[0].url == "https://bot.example.com/lst-500"
    assert rows[0].last_status_code == 500
    assert rows[0].event_name == "message_created"


@respx.mock
async def test_listener_inline_fallback_no_dead_letter_on_2xx(db_session):
    """End-to-end happy path: receiver returns 200 → no dead-letter row."""
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="lst-owner-ok@v29.example.com",
            account_name="Listener OK",
            user_full_name="LOK Admin",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    bot, conv = await _seed_bot_attached(
        db_session, owner, outgoing_url="https://bot.example.com/lst-ok"
    )
    respx.post("https://bot.example.com/lst-ok").mock(
        return_value=httpx.Response(200)
    )
    await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(
            content="trigger", message_type="incoming"
        ),
        user_id=None,
    )

    rows = list(
        (
            await db_session.exec(
                select(WebhookDeadLetter).where(
                    WebhookDeadLetter.account_id == owner.account.id
                )
            )
        ).all()
    )
    assert rows == []


# ---------------------------------------------------------------------------
# Outcome dataclass — sanity assertion so the shape doesn't drift
# ---------------------------------------------------------------------------
def test_delivery_outcome_shape():
    out = DeliveryOutcome(
        kind="retry", status_code=502, error="bad gateway", next_backoff_seconds=30
    )
    assert out.kind == "retry"
    assert out.status_code == 502
    assert out.error == "bad gateway"
    assert out.next_backoff_seconds == 30
