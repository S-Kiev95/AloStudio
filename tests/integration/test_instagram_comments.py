"""Integration tests for Instagram comment moderation (I.7).

Two layers:
  * service — ``publishing_service`` comment fns end-to-end with respx
    mocking Meta's comment edges (list/post/reply/hide/delete).
  * endpoint — the admin-only REST surface in ``comments_router``.

No real Meta calls; respx intercepts every outbound httpx request.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.core.errors import ChatwootHTTPException
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts import models as _contacts  # noqa: F401  (mapper)
from app.domains.conversations import models as _conversations  # noqa: F401
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.instagram import publishing_service as svc
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.main import app

pytestmark = pytest.mark.integration

GRAPH = "https://graph.facebook.com/v23.0"


# ---------------------------------------------------------------------------
# Fixtures + seed helpers
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


async def _seed(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@igc.example.com",
            account_name=f"IGC{suffix}",
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
            channel_params={
                "instagram_id": f"ig-c-{suffix}",
                "access_token": "PAGE-TOKEN",
            },
        ),
    ).perform()
    headers, new_tokens = create_new_auth_token(
        user_tokens=owner.user.tokens, uid=owner.user.uid
    )
    owner.user.tokens = new_tokens
    db_session.add(owner.user)
    await db_session.flush()
    return owner, result.inbox, result.channel, headers.as_response_headers()


async def _published_post(db_session, owner, inbox, channel, ig_media_id):
    post = await svc.create_post(
        db_session,
        account_id=owner.account.id,
        inbox_id=inbox.id,
        channel_instagram_id=channel.id,
        media_type="IMAGE",
        source={"image_url": "https://x.example.com/p.jpg"},
    )
    post.state = "published"
    post.ig_media_id = ig_media_id
    db_session.add(post)
    await db_session.flush()
    return post


async def _seed_comment(db_session, owner, channel, *, ig_comment_id, ig_media_id):
    return await svc.upsert_comment(
        db_session,
        account_id=owner.account.id,
        channel_instagram_id=channel.id,
        ig_comment_id=ig_comment_id,
        ig_media_id=ig_media_id,
        from_username="bob",
        text="original",
    )


# ---------------------------------------------------------------------------
# Service — list (live sync from Meta)
# ---------------------------------------------------------------------------
@respx.mock
async def test_list_comments_syncs_from_meta(db_session):
    owner, _inbox, channel, _ = await _seed(db_session, "-list")
    respx.get(f"{GRAPH}/MED1/comments").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "C100",
                        "text": "nice",
                        "username": "alice",
                        "hidden": False,
                        "from": {"id": "999", "username": "alice"},
                        "timestamp": "2026-05-20T12:00:00+0000",
                        "replies": {
                            "data": [
                                {
                                    "id": "C101",
                                    "text": "thanks",
                                    "username": "owner",
                                    "hidden": False,
                                }
                            ]
                        },
                    }
                ]
            },
        )
    )
    rows = await svc.list_comments_on_meta(
        db_session,
        channel=channel,
        account_id=owner.account.id,
        ig_media_id="MED1",
    )
    assert {r.ig_comment_id for r in rows} == {"C100", "C101"}
    reply = next(r for r in rows if r.ig_comment_id == "C101")
    assert reply.parent_comment_id == "C100"
    top = next(r for r in rows if r.ig_comment_id == "C100")
    assert top.from_id == "999"
    assert top.ig_created_at is not None


@respx.mock
async def test_list_comments_meta_error_surfaces(db_session):
    owner, _inbox, channel, _ = await _seed(db_session, "-listerr")
    respx.get(f"{GRAPH}/MEDERR/comments").mock(
        return_value=httpx.Response(
            400, json={"error": {"message": "bad", "code": 100}}
        )
    )
    with pytest.raises(ChatwootHTTPException) as exc:
        await svc.list_comments_on_meta(
            db_session,
            channel=channel,
            account_id=owner.account.id,
            ig_media_id="MEDERR",
        )
    assert exc.value.status_code == 422


# ---------------------------------------------------------------------------
# Service — post / reply / hide / delete
# ---------------------------------------------------------------------------
@respx.mock
async def test_post_comment_persists(db_session):
    owner, _inbox, channel, _ = await _seed(db_session, "-post")
    route = respx.post(f"{GRAPH}/MED2/comments").mock(
        return_value=httpx.Response(200, json={"id": "NEWC1"})
    )
    comment = await svc.post_comment_on_meta(
        db_session,
        channel=channel,
        account_id=owner.account.id,
        ig_media_id="MED2",
        message="hello there",
    )
    assert route.called
    assert comment.ig_comment_id == "NEWC1"
    assert comment.text == "hello there"
    body = route.calls.last.request.content.decode()
    assert "message" in body


@respx.mock
async def test_reply_comment_persists(db_session):
    owner, _inbox, channel, _ = await _seed(db_session, "-reply")
    parent = await _seed_comment(
        db_session, owner, channel, ig_comment_id="P1", ig_media_id="MEDR"
    )
    respx.post(f"{GRAPH}/P1/replies").mock(
        return_value=httpx.Response(200, json={"id": "R1"})
    )
    reply = await svc.reply_comment_on_meta(
        db_session,
        channel=channel,
        account_id=owner.account.id,
        parent_comment=parent,
        message="thanks!",
    )
    assert reply.ig_comment_id == "R1"
    assert reply.parent_comment_id == "P1"
    assert reply.ig_media_id == "MEDR"


@respx.mock
async def test_hide_comment_toggles(db_session):
    owner, _inbox, channel, _ = await _seed(db_session, "-hide")
    comment = await _seed_comment(
        db_session, owner, channel, ig_comment_id="H1", ig_media_id="MEDH"
    )
    route = respx.post(f"{GRAPH}/H1").mock(
        return_value=httpx.Response(200, json={"success": True})
    )
    updated = await svc.hide_comment_on_meta(
        db_session, channel=channel, comment=comment, hide=True
    )
    assert route.called
    assert updated.hidden is True
    body = route.calls.last.request.content.decode()
    assert "hide" in body
    assert "true" in body


@respx.mock
async def test_delete_comment_removes_row(db_session):
    owner, _inbox, channel, _ = await _seed(db_session, "-cdel")
    comment = await _seed_comment(
        db_session, owner, channel, ig_comment_id="D1", ig_media_id="MEDD"
    )
    cid = comment.id
    respx.delete(f"{GRAPH}/D1").mock(
        return_value=httpx.Response(200, json={"success": True})
    )
    await svc.delete_comment_on_meta(
        db_session, channel=channel, comment=comment
    )
    gone = await svc.get_comment(
        db_session, account_id=owner.account.id, comment_id=cid
    )
    assert gone is None


@respx.mock
async def test_post_comment_meta_error_surfaces(db_session):
    owner, _inbox, channel, _ = await _seed(db_session, "-posterr")
    respx.post(f"{GRAPH}/MEDPE/comments").mock(
        return_value=httpx.Response(
            400,
            json={"error": {"message": "Comments disabled", "code": 9007}},
        )
    )
    with pytest.raises(ChatwootHTTPException) as exc:
        await svc.post_comment_on_meta(
            db_session,
            channel=channel,
            account_id=owner.account.id,
            ig_media_id="MEDPE",
            message="x",
        )
    assert exc.value.status_code == 422


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
async def test_comments_index_requires_auth(client):
    resp = await client.get(
        "/api/v1/accounts/1/instagram_posts/1/comments"
    )
    assert resp.status_code == 401


@respx.mock
async def test_index_comments_endpoint(client, db_session):
    owner, inbox, channel, headers = await _seed(db_session, "-ixc")
    post = await _published_post(db_session, owner, inbox, channel, "EMED1")
    respx.get(f"{GRAPH}/EMED1/comments").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"id": "EC1", "text": "hi", "hidden": False}]},
        )
    )
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/instagram_posts/{post.id}/comments",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert any(c["ig_comment_id"] == "EC1" for c in body)


async def test_index_comments_unpublished_post_422(client, db_session):
    owner, inbox, channel, headers = await _seed(db_session, "-ixunp")
    post = await svc.create_post(
        db_session,
        account_id=owner.account.id,
        inbox_id=inbox.id,
        channel_instagram_id=channel.id,
        media_type="IMAGE",
        source={"image_url": "https://x.example.com/p.jpg"},
    )
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/instagram_posts/{post.id}/comments",
        headers=headers,
    )
    assert resp.status_code == 422


@respx.mock
async def test_create_comment_endpoint(client, db_session):
    owner, inbox, channel, headers = await _seed(db_session, "-crc")
    post = await _published_post(db_session, owner, inbox, channel, "EMED2")
    respx.post(f"{GRAPH}/EMED2/comments").mock(
        return_value=httpx.Response(200, json={"id": "ECNEW"})
    )
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/instagram_posts/{post.id}/comments",
        json={"message": "well done"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["ig_comment_id"] == "ECNEW"


@respx.mock
async def test_reply_endpoint(client, db_session):
    owner, _inbox, channel, headers = await _seed(db_session, "-rep")
    parent = await _seed_comment(
        db_session, owner, channel, ig_comment_id="EP1", ig_media_id="EMEDR"
    )
    respx.post(f"{GRAPH}/EP1/replies").mock(
        return_value=httpx.Response(200, json={"id": "ER1"})
    )
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/instagram_comments/{parent.id}/replies",
        json={"message": "ty"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["parent_comment_id"] == "EP1"


@respx.mock
async def test_hide_endpoint(client, db_session):
    owner, _inbox, channel, headers = await _seed(db_session, "-hid")
    comment = await _seed_comment(
        db_session, owner, channel, ig_comment_id="EH1", ig_media_id="EMEDH"
    )
    respx.post(f"{GRAPH}/EH1").mock(
        return_value=httpx.Response(200, json={"success": True})
    )
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/instagram_comments/{comment.id}/hide",
        json={"hide": True},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["hidden"] is True


@respx.mock
async def test_delete_comment_endpoint(client, db_session):
    owner, _inbox, channel, headers = await _seed(db_session, "-del")
    comment = await _seed_comment(
        db_session, owner, channel, ig_comment_id="ED1", ig_media_id="EMEDD"
    )
    respx.delete(f"{GRAPH}/ED1").mock(
        return_value=httpx.Response(200, json={"success": True})
    )
    resp = await client.delete(
        f"/api/v1/accounts/{owner.account.id}/instagram_comments/{comment.id}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True


async def test_reply_unknown_comment_404(client, db_session):
    owner, _inbox, _channel, headers = await _seed(db_session, "-unk")
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/instagram_comments/99999999/replies",
        json={"message": "x"},
        headers=headers,
    )
    assert resp.status_code == 404
