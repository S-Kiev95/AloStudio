"""Integration tests for the publishing queue: firing due publications and
publishing each target independently."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.core.models_registry import import_all_models
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.publishing import service as svc
from app.domains.publishing.adapters import PublishResult
from app.domains.publishing.adapters.facebook_page import FacebookPageAdapter
from app.domains.publishing.adapters.instagram import InstagramAdapter
from app.domains.publishing.models import Publication
from app.workers import publishing as publishing_worker

import_all_models()

pytestmark = pytest.mark.integration

IMAGE = {"type": "image", "url": "https://cdn.example.com/a.jpg"}


async def _seed(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@pubw.example.com",
            account_name=f"PUBW{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    fb = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="Pagina",
            channel_type="facebook",
            channel_params={"page_id": f"P{suffix}", "page_access_token": "t"},
        ),
    ).perform()
    ig = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="Insta",
            channel_type="instagram",
            channel_params={
                "instagram_id": f"1784{abs(hash(suffix)) % 10_000_000}",
                "access_token": "t",
            },
        ),
    ).perform()
    return owner.account, fb.inbox, ig.inbox


async def _publication(db_session, account, inboxes, *, scheduled_for=None):
    return await svc.create_publication(
        db_session,
        account_id=account.id,
        payload={
            "content": "hola",
            "media": [IMAGE],
            "scheduled_for": scheduled_for
            or datetime.now(UTC) + timedelta(hours=1),
            "targets": [{"inbox_id": i.id} for i in inboxes],
        },
    )


async def _claim(db_session, publication) -> None:
    """Make it due and claim it, as the scheduler tick would."""
    publication.scheduled_for = datetime.now(UTC) - timedelta(minutes=1)
    db_session.add(publication)
    await db_session.flush()
    assert await svc.start_publishing(db_session, publication_id=publication.id)


def _stub(monkeypatch, adapter_cls, results: list[PublishResult]) -> list[int]:
    """Make an adapter return ``results`` in order; returns the target ids
    it was asked to publish."""
    calls: list[int] = []

    async def _publish(self, session, publication, target):
        calls.append(target.id)
        return results[min(len(calls), len(results)) - 1]

    monkeypatch.setattr(adapter_cls, "publish", _publish)
    return calls


async def test_fire_claims_only_due_publications_once(db_session, monkeypatch):
    account, fb, _ig = await _seed(db_session, "-fire")
    due = await _publication(db_session, account, [fb])
    due.scheduled_for = datetime.now(UTC) - timedelta(minutes=1)
    db_session.add(due)
    future = await _publication(db_session, account, [fb])
    await db_session.flush()

    enqueued: list[int] = []

    async def _fake(publication_id: int) -> None:
        enqueued.append(publication_id)

    monkeypatch.setattr(publishing_worker, "enqueue_publication", _fake)

    assert await publishing_worker.fire_due_publications(db_session) == [due.id]
    assert await publishing_worker.fire_due_publications(db_session) == []
    assert enqueued == [due.id]
    await db_session.refresh(due)
    await db_session.refresh(future)
    assert due.state == "publishing"
    assert future.state == "scheduled"


async def test_one_target_failing_does_not_stop_the_other(db_session, monkeypatch):
    account, fb, ig = await _seed(db_session, "-partial")
    publication = await _publication(db_session, account, [fb, ig])
    _stub(monkeypatch, FacebookPageAdapter, [
        PublishResult(ok=True, external_id="PAGE_1", permalink="https://fb/p/1"),
    ])
    _stub(monkeypatch, InstagramAdapter, [
        PublishResult(ok=False, error_code="100", error_message="imagen rota"),
    ])
    await _claim(db_session, publication)

    retry = await svc.publish_pending_targets(
        db_session, publication_id=publication.id
    )

    assert retry is False
    await db_session.refresh(publication)
    assert publication.state == "partially_published"
    assert publication.published_at is not None
    targets = {
        t.inbox_id: t
        for t in (
            await svc.targets_by_publication(
                db_session, publication_ids=[publication.id]
            )
        )[publication.id]
    }
    assert targets[fb.id].state == "published"
    assert targets[fb.id].external_id == "PAGE_1"
    assert targets[ig.id].state == "failed"
    assert targets[ig.id].error_message == "imagen rota"


async def test_retryable_error_waits_then_fails_on_last_try(db_session, monkeypatch):
    account, fb, _ig = await _seed(db_session, "-retry")
    publication = await _publication(db_session, account, [fb])
    calls = _stub(monkeypatch, FacebookPageAdapter, [
        PublishResult(ok=False, error_code="4", error_message="limite", retryable=True),
    ])
    await _claim(db_session, publication)

    assert await svc.publish_pending_targets(
        db_session, publication_id=publication.id, final_attempt=False
    ) is True
    await db_session.refresh(publication)
    assert publication.state == "publishing"
    (target,) = (
        await svc.targets_by_publication(db_session, publication_ids=[publication.id])
    )[publication.id]
    assert target.state == "pending"
    assert target.attempts == 1

    assert await svc.publish_pending_targets(
        db_session, publication_id=publication.id, final_attempt=True
    ) is False
    await db_session.refresh(publication)
    await db_session.refresh(target)
    assert publication.state == "failed"
    assert target.state == "failed"
    assert target.attempts == 2
    assert len(calls) == 2


async def test_published_target_is_never_sent_again(db_session, monkeypatch):
    account, fb, ig = await _seed(db_session, "-once")
    publication = await _publication(db_session, account, [fb, ig])
    fb_calls = _stub(monkeypatch, FacebookPageAdapter, [
        PublishResult(ok=True, external_id="PAGE_1"),
    ])
    _stub(monkeypatch, InstagramAdapter, [
        PublishResult(ok=False, error_code="x", error_message="falló"),
    ])
    await _claim(db_session, publication)
    await svc.publish_pending_targets(db_session, publication_id=publication.id)

    publication = await db_session.get(Publication, publication.id)
    await svc.retry_publication(db_session, publication=publication)
    await svc.publish_pending_targets(db_session, publication_id=publication.id)

    assert len(fb_calls) == 1


async def test_unexpected_adapter_error_is_contained(db_session, monkeypatch):
    account, fb, ig = await _seed(db_session, "-boom")
    publication = await _publication(db_session, account, [fb, ig])

    async def _explode(self, session, publication, target):
        raise RuntimeError("bug")

    monkeypatch.setattr(InstagramAdapter, "publish", _explode)
    _stub(monkeypatch, FacebookPageAdapter, [PublishResult(ok=True, external_id="P")])
    await _claim(db_session, publication)

    await svc.publish_pending_targets(db_session, publication_id=publication.id)

    await db_session.refresh(publication)
    assert publication.state == "partially_published"
    targets = {
        t.inbox_id: t
        for t in (
            await svc.targets_by_publication(
                db_session, publication_ids=[publication.id]
            )
        )[publication.id]
    }
    assert targets[ig.id].state == "failed"
    assert targets[ig.id].error_code == "unexpected_error"


async def test_claim_skips_a_date_moved_forward(db_session):
    account, fb, _ig = await _seed(db_session, "-moved")
    publication = await _publication(db_session, account, [fb])

    # Picked as due, then edited to a future date before the claim.
    assert not await svc.start_publishing(db_session, publication_id=publication.id)
    await db_session.refresh(publication)
    assert publication.state == "scheduled"


async def test_failed_enqueue_hands_the_publication_back(db_session, monkeypatch):
    account, fb, _ig = await _seed(db_session, "-enqfail")
    publication = await _publication(db_session, account, [fb])
    publication.scheduled_for = datetime.now(UTC) - timedelta(minutes=1)
    db_session.add(publication)
    await db_session.flush()

    async def _broken(publication_id: int) -> None:
        raise ConnectionError("redis down")

    monkeypatch.setattr(publishing_worker, "enqueue_publication", _broken)

    assert await publishing_worker.fire_due_publications(db_session) == []
    await db_session.refresh(publication)
    assert publication.state == "scheduled"


async def test_stale_publishing_is_recovered_without_republishing(db_session, monkeypatch):
    account, fb, ig = await _seed(db_session, "-stale")
    publication = await _publication(db_session, account, [fb, ig])
    await _claim(db_session, publication)
    targets = {
        t.inbox_id: t
        for t in (
            await svc.targets_by_publication(db_session, publication_ids=[publication.id])
        )[publication.id]
    }
    # The job died while sending to Facebook; Instagram never started.
    targets[fb.id].state = "publishing"
    db_session.add(targets[fb.id])
    publication = await db_session.get(Publication, publication.id)
    publication.updated_at = datetime.now(UTC) - timedelta(hours=2)
    db_session.add(publication)
    await db_session.flush()

    enqueued: list[int] = []

    async def _fake(publication_id: int) -> None:
        enqueued.append(publication_id)

    monkeypatch.setattr(publishing_worker, "enqueue_publication", _fake)

    assert await publishing_worker.fire_due_publications(db_session) == [publication.id]
    await db_session.refresh(targets[fb.id])
    await db_session.refresh(targets[ig.id])
    assert targets[fb.id].state == "failed"
    assert targets[fb.id].error_code == "interrupted"
    assert targets[ig.id].state == "pending"
    assert enqueued == [publication.id]


async def test_publication_without_targets_is_not_published(db_session, monkeypatch):
    account, fb, _ig = await _seed(db_session, "-empty")
    publication = await _publication(db_session, account, [fb])
    publication.scheduled_for = datetime.now(UTC) - timedelta(minutes=1)
    db_session.add(publication)
    await db_session.flush()
    await _claim(db_session, publication)
    # The channel was deleted after scheduling (targets cascade away).
    await db_session.delete(fb)
    await db_session.flush()

    await svc.publish_pending_targets(db_session, publication_id=publication.id)

    await db_session.refresh(publication)
    assert publication.state == "failed"


async def test_only_publishing_publications_are_published(db_session, monkeypatch):
    account, fb, _ig = await _seed(db_session, "-guard")
    publication = await _publication(db_session, account, [fb])
    calls = _stub(monkeypatch, FacebookPageAdapter, [PublishResult(ok=True)])

    await svc.publish_pending_targets(db_session, publication_id=publication.id)

    assert calls == []
    await db_session.refresh(publication)
    assert publication.state == "scheduled"
