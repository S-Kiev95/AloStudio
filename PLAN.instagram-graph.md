# Feature branch — Instagram Graph API publishing + moderation

**Branch:** `feat/instagram-graph` (off `main` at the close of Phase 10)

**Goal:** Extend the existing `InstagramChannel` (which today only
handles Direct Messages — Phase 5e) with publishing (single image,
video, reels, carousel, stories), media deletion, comment moderation,
and webhook reception for `comments`/`mentions`/`story_insights`.

**This is OUT of Chatwoot-mirror scope.** Chatwoot v4.13.0 doesn't
publish to Instagram or moderate comments — this is an own-extension
on top of the channel model. No parity contract applies; the only
constraint is the existing schema stays compatible.

---

## Verified API spec (May 2026 snapshot — see research notes below)

### Graph API version
**`v23.0`** pinned. Released May 29, 2025. Meta lists v25.0 (Feb
2026) as latest but expiration dates are TBD on all four currently-
supported versions (v22-v25). Pin v23 + watch the
[versions changelog](https://developers.facebook.com/docs/graph-api/changelog/versions/).

### Two parallel flows — we pick ONE

Meta supports two OAuth + API host combinations:

| Flow | Login | API host | Best for |
|---|---|---|---|
| **Instagram Login** | `api.instagram.com/oauth` | `graph.instagram.com` | New apps, no FB Page needed |
| **Facebook Login** | `facebook.com/dialog/oauth` | `graph.facebook.com` | Apps already linked to FB Pages |

**Decision: Facebook Login flow** because:
1. Phase 5e already uses `graph.facebook.com` for FB Messenger.
2. The `DELETE /{ig-media-id}` endpoint is **only documented on
   `graph.facebook.com`** — Instagram Login flow can't delete media
   per current docs.
3. Page access tokens **don't expire** when derived from a long-lived
   user token, which fits long-running publishing automations.

### OAuth scopes (Facebook Login flow)

| Scope | What it grants |
|---|---|
| `instagram_basic` | Profile + media read |
| `instagram_content_publish` | `POST /media` + `/media_publish` |
| `instagram_manage_comments` | List/post/reply/hide/delete comments |
| `instagram_manage_insights` | Story insights + media metrics |
| `instagram_manage_messages` | (already needed for Phase 5e DMs) |
| `pages_show_list` | Discover FB Pages linked to the user |
| `pages_read_engagement` | Read Page metadata |
| `pages_manage_metadata` | Install webhook subscriptions on a Page |
| `business_management` | Business Manager context |

### Container creation — `POST /{ig-user-id}/media`

| Media type | Required params | Optional params |
|---|---|---|
| Image | `image_url` | `caption` (≤2200), `alt_text` (≤1000), `location_id`, `user_tags`, `product_tags` (≤5), `collaborators` (≤3) |
| Video | `media_type=VIDEO`, `video_url` | `caption`, `thumb_offset` (ms), `location_id`, `user_tags`, `product_tags`, `collaborators` |
| Reel | `media_type=REELS`, `video_url` | `caption`, `cover_url` (overrides `thumb_offset`), `audio_name` (1-time write), `share_to_feed`, `collaborators`, `user_tags`, `location_id`, `trial_params` |
| Carousel child | `is_carousel_item=true`, `image_url` OR `video_url` | (no caption on children) |
| Carousel parent | `media_type=CAROUSEL`, `children` (≤10) | `caption`, `share_to_feed`, `collaborators`, `location_id`, `product_tags` |
| Story | `media_type=STORIES`, `image_url` OR `video_url` | `user_tags` |

All types accept: `branded_content_sponsor_ids` (≤2), `is_paid_partnership`.

### Container polling — `GET /{container-id}?fields=status_code`

Five status values:
- `IN_PROGRESS` — keep polling
- `FINISHED` — ready to publish
- `PUBLISHED` — already done
- `ERROR` — failed (terminal)
- `EXPIRED` — container older than 24h (terminal)

**Meta's recommendation: poll once per minute for max 5 minutes.**
We'll honour that exactly via ARQ task scheduling.

### Publish — `POST /{ig-user-id}/media_publish?creation_id=...`

Returns the final `ig_media_id`. Counts against quota.

### Rate limits

| Limit | Scope | Window |
|---|---|---|
| **Publish quota** | 100 posts per IG account (carousel counts as 1) | 24h sliding |
| **Platform usage** | `4800 × Impressions` calls | 1h rolling, per BUC |
| App-level | percentage-based via `X-App-Usage` header | 1h |

Throttling error codes to detect: **4** (app), **17** (user),
**80001** (Page BUC), **80002** (Instagram BUC). Quota check
endpoint: `GET /{ig-user-id}/content_publishing_limit`.

### Container TTL
**24 hours.** Expired containers flip to `status_code=EXPIRED` and
can't be published — must recreate.

### Comments

| Op | Endpoint | Notes |
|---|---|---|
| List | `GET /{ig-media-id}/comments?fields=replies{...}` | 50/page, top-level + replies via field expansion |
| Post | `POST /{ig-media-id}/comments?message=...` | Not on live-video media |
| Reply | `POST /{ig-comment-id}/replies?message=...` | |
| Hide / unhide | `POST /{ig-comment-id}?hide=true\|false` | Toggle |
| Delete | `DELETE /{ig-comment-id}` | Owner can delete any; non-owners only their own |
| Block user | **No documented API** | Hide is the documented lever; account-level block is UI-only |

### Delete media

`DELETE https://graph.facebook.com/{ig-media-id}`. Requires
`instagram_manage_contents` scope + Page access token. Can delete
organic feed posts, stories, reels, **entire carousels** (but NOT
individual carousel children). Cannot delete ad-promoted posts or
live videos. No documented age limit.

### Webhook fields for `object=instagram`

| Field | Payload |
|---|---|
| `comments` | New comment on owned media (`id`, `text`, `media.id`, `from.id`, `from.username`) |
| `mentions` | @-mention in comment or caption (`media_id`, `comment_id`) |
| `story_insights` | Story expired (`impressions`, `reach`, `taps_forward`, `taps_back`, `exits`, `replies`) |
| `messages`, `message_echoes`, `message_reactions` | DM events (Phase 5e already handles `messages`) |
| `live_comments` | Live broadcast comments |

**Signing**: `X-Hub-Signature-256: sha256=<hmac-sha256(body, app_secret)>`
header — verify BEFORE processing.

**Subscription**: `POST /{page-id}/subscribed_apps` with Page token.

### Token flow

```
Short-lived user token (~1h)
  ↓ exchange via /oauth/access_token?grant_type=fb_exchange_token
Long-lived user token (~60d)
  ↓ /me/accounts
Page access token (no expiry — what we store)
```

Page token is what lives in `InstagramChannel.access_token` for
publishing/deletion/moderation/webhook subscription. Phase 5e
already has this column — extend, don't recreate.

---

## Architecture decisions

### Publishing flow with ARQ

```
POST /api/v1/accounts/{id}/instagram_posts (image_url or carousel children)
   ↓
INSERT instagram_posts (state: pending)
   ↓
arq.enqueue("publish_instagram_post", post_id)
   ↓
ARQ worker task:
   1. POST /{ig}/media → container_id
      INSERT instagram_post_containers (parent_id, ig_container_id, state: in_progress)
   2. For each video/reel/story child: poll status_code, retry every 60s, max 5 polls
      (Meta's published cadence)
   3. When all children FINISHED → POST /media_publish
   4. UPDATE instagram_posts (state: published, ig_media_id, published_at)
```

**Why state lives in Postgres, not Redis** (you asked about this):

| Concern | Redis (n8n approach) | Postgres + ARQ (ours) |
|---|---|---|
| Status persistence | volatile + needs TTLs | durable, queryable, FK to channel |
| Replay after crash | rebuild from queue | row exists, ARQ retries |
| Audit / dashboard | extra Redis introspection | normal SQL query |
| Carousel coordination | manual key juggling | parent + child rows |

Redis stays implicit (ARQ uses it as queue + lock backend) — we
don't write Redis keys manually.

### Schema additions

```sql
-- Publishing
CREATE TABLE instagram_posts (
  id BIGINT PRIMARY KEY,
  account_id BIGINT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  inbox_id BIGINT NOT NULL REFERENCES inboxes(id) ON DELETE CASCADE,
  channel_instagram_id BIGINT NOT NULL,        -- FK to channel_instagram
  state VARCHAR NOT NULL,                       -- pending / publishing / published / failed
  media_type VARCHAR NOT NULL,                  -- image / video / reel / carousel / story
  caption TEXT,
  source JSONB NOT NULL,                        -- {image_url} or {video_url} or {children: [...]}
  ig_media_id VARCHAR,                          -- populated after publish
  ig_permalink VARCHAR,
  error_code VARCHAR,
  error_message TEXT,
  scheduled_for TIMESTAMPTZ,                    -- null for immediate; future for scheduled
  published_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE instagram_post_containers (
  id BIGINT PRIMARY KEY,
  post_id BIGINT NOT NULL REFERENCES instagram_posts(id) ON DELETE CASCADE,
  ig_container_id VARCHAR NOT NULL,
  position INT NOT NULL,                         -- 0 = parent, 1..N = children in order
  status_code VARCHAR NOT NULL,                  -- IN_PROGRESS / FINISHED / PUBLISHED / ERROR / EXPIRED
  poll_count INT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Comments moderation
CREATE TABLE instagram_comments (
  id BIGINT PRIMARY KEY,
  account_id BIGINT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  channel_instagram_id BIGINT NOT NULL,
  ig_comment_id VARCHAR UNIQUE NOT NULL,
  ig_media_id VARCHAR NOT NULL,
  parent_comment_id VARCHAR,                     -- null for top-level, ig_comment_id of parent
  from_username VARCHAR,
  from_id VARCHAR,
  text TEXT,
  hidden BOOLEAN NOT NULL DEFAULT false,
  -- ``Conversation`` link is optional — when we route the comment
  -- into the inbox as a conversation for the agent, this gets set.
  conversation_id BIGINT REFERENCES conversations(id) ON DELETE SET NULL,
  ig_created_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## Milestones

### I.0 — Token rotation reminder + dev env setup

- [ ] User rotates the leaked test token (DONE outside this branch).
- [ ] `.env` template adds `META_APP_ID`, `META_APP_SECRET`,
      `META_GRAPH_API_VERSION=v23.0`.
- [ ] Document the test account setup in `app/domains/instagram/README.md`.

### I.1 — Schema + service skeletons

- [x] `instagram_posts`, `instagram_post_containers`,
      `instagram_comments` tables + Alembic migration.
- [x] SQLModel classes.
- [x] Service skeleton (no business logic yet): create_post,
      list_posts, get_post, delete_post.
- [x] Tests: model round-trip + cascade deletes.

### I.2 — Single image publish + scheduling ✅

- [x] `app/domains/instagram/publisher.py` — POST `/media` for
      single image with full param support.
- [x] `app/domains/instagram/poller.py` — status_code polling helper
      with Meta's 1-min cadence + 5-attempt cap.
- [x] ARQ task `publish_instagram_post` for the happy path
      (creates container, polls, publishes — runs immediately when
      enqueued).
- [x] Scheduler hook: extend Phase 10.1's ``tick_5min`` with
      ``fire_due_instagram_posts(session)`` that SELECTs
      ``WHERE state='pending' AND scheduled_for <= now()`` and
      enqueues ``publish_instagram_post`` per match. Container
      creation is deferred to the ARQ task body (NOT at create-post
      time) because Meta containers expire after 24h — creating
      them up-front would break any post scheduled >24h ahead.
- [x] HTTP endpoint `POST /api/v1/accounts/{id}/instagram_posts`:
      * `scheduled_for=null` (default) → enqueue ARQ task immediately
      * `scheduled_for` in the future → row stays pending; tick_5min
        picks it up at fire time
      * `scheduled_for` in the past → 422 ("scheduled_for must be in
        the future")
      * NO upper-bound cap — user can schedule arbitrarily far ahead
        (design decision: dashboard shows pending posts as a queue;
        no business reason to artificially limit horizon)
- [x] respx-mocked tests covering:
      * full state machine (pending → publishing → published) for
        immediate publish (`test_instagram_publisher.py`)
      * scheduled post NOT enqueued before scheduled_for / stays
        pending (`test_instagram_publishing_router.py`)
      * past scheduled_for → 422
      * far-future scheduling accepted (no upper cap)
      * failure paths: container API error, container ERROR status,
        poll timeout, media_publish error, unsupported media type
      * idempotency on non-pending re-enqueue

**Test tally:** 39 green (22 models + 8 publisher service + 9 router).

### I.3 — Video + Reels publishing ✅

- [x] Extend publisher to handle `media_type=VIDEO`/`REELS`
      (`build_video_container_params`). `publish_post` now dispatches
      on media_type — IMAGE/VIDEO/REELS share the single-container
      path (create → poll → publish), only the param dict differs.
- [x] Polling path actually exercised — `test_publish_video_polls_
      until_finished` returns IN_PROGRESS twice then FINISHED
      (poll_route.call_count == 3).
- [x] Reels-specific params (cover_url, share_to_feed, audio_name,
      thumb_offset) pulled from `source` JSONB; booleans serialised
      to Meta's `"true"`/`"false"` for the form body.
- [x] Tests: video happy path, reels params on container body, multi-
      poll, `EXPIRED` terminal, video-without-url failure. CAROUSEL +
      STORIES still assert `unsupported_media_type`.

**Test tally:** 45 green (22 models + 14 publisher service + 9 router).

### I.4 — Carousel publishing ✅

- [x] Carousel parent + children orchestration in
      `_publish_carousel`: create one container per child →
      poll each to FINISHED → create the parent referencing the
      child ids → poll parent → publish.
- [x] Parent only created once **all** children are FINISHED (a child
      stuck in ERROR fails the post before any parent call). Children
      polled sequentially (single async session + Meta's 60s cadence
      make `asyncio.gather` unnecessary).
- [x] ≤10 children + non-empty + per-child image_url/video_url
      enforced at `create_post` (422); re-guarded defensively in
      `_publish_carousel`. Container positions: parent=0, children=1..N.
- [x] Tests: happy path (2 images), mixed image+video (asserts the
      video child carries `media_type=VIDEO` + `is_carousel_item`),
      child stuck in ERROR (no parent created), child create 400.

**Test tally:** 48 green (22 models + 17 publisher service + 9 router).

### I.5 — Stories ✅

- [x] `media_type=STORIES` branch in `publish_post` — takes the
      single-container path with `build_story_container_params`
      (image **or** video, no caption). 24h auto-expiry needs no
      handling: Meta drops the story automatically; the row stays
      `published` for audit.
- [x] Tests: image story happy path + video story happy path (assert
      the container body carries `media_type=STORIES` + the right url),
      story-without-source failure (`missing_story_source`).

**Test tally:** 50 green (22 models + 19 publisher service + 9 router).

> With I.5 done, **all five media types publish** (IMAGE, VIDEO, REELS,
> CAROUSEL, STORIES). The remaining milestones are deletion (I.6),
> comment moderation (I.7), webhooks (I.8), quota (I.9), OAuth (I.10).

### I.6 — Delete media ✅

- [x] `DELETE /api/v1/accounts/{id}/instagram_posts/{post_id}` →
      `publisher.delete_media` (`DELETE /{ig-media-id}`) + flip the row
      `published → deleted`. Only `published` posts (which have an
      `ig_media_id`) hit Meta; other states 422. Idempotent on an
      already-`deleted` row (no second Meta call).
- [x] Delete is interactive (not the worker), so a Meta-side failure
      surfaces as a 422 carrying the Meta error code — but the row
      still gets `error_code`/`error_message` stamped for audit and
      keeps its `published` state.
- [x] Tests (service + endpoint): happy path, non-published 422,
      unknown 404, Meta-error surfaces+stamps (e.g. live video, code
      10), idempotency, auth gate. The documented restrictions
      (carousel children / live video / ad-promoted) are exactly the
      Meta-error path — Meta returns 4xx, we relay it.

**Test tally:** 59 green (22 models + 24 publisher service + 13 router).

### I.7 — Comments — read + write + moderation ✅

- [x] `comments_client.py` — Meta HTTP client (never raises): list
      (`replies{...}` expansion, flattened so replies carry
      `parent_comment_id`), post, reply, hide/unhide, delete.
- [x] Service wires the 4 ex-stubs + `list_comments_on_meta` +
      `get_comment`. List/post/reply upsert into the local
      `instagram_comments` mirror; hide flips `hidden`; delete drops
      the row. Meta-side failures surface as 422 (interactive surface).
- [x] `comments_router.py` (admin-only, wired in main.py):
      * `GET  /instagram_posts/{post_id}/comments` (live sync)
      * `POST /instagram_posts/{post_id}/comments`
      * `POST /instagram_comments/{comment_id}/replies`
      * `POST /instagram_comments/{comment_id}/hide`
      * `DELETE /instagram_comments/{comment_id}`
- [x] `test_instagram_comments.py` — service layer (list sync incl.
      reply linkage + ig_created_at parse, post, reply, hide, delete,
      Meta-error 422) + endpoints (auth gate, index, unpublished-post
      422, create, reply, hide, delete, unknown-comment 404).
- [x] Stub-contract test removed — no NotImplementedError stubs remain.

**Test tally:** 73 green (22 models + 24 publisher + 13 router +
14 comments).

### I.8 — Webhook receiver for comments + mentions + story_insights ✅

- [x] `webhook_changes.process_instagram_changes` handles the
      `entry[].changes[]` half of the `object=instagram` webhook
      (the DM `messaging[]` half stays in Phase 5e's `incoming.py`,
      untouched). Both run from the shared POST handler.
- [x] `comments` upserts an `instagram_comments` row (text/from/media/
      parent). (Routing a comment into a `Conversation` is deferred —
      the table already has the nullable `conversation_id` FK for when
      an account opts in.)
- [x] `mentions` upserts a comment row when a `comment_id` is present;
      caption-only mentions (no comment id) are skipped.
- [x] `story_insights` stamps metrics onto the matching published
      STORIES post via a new nullable `insights` JSONB column
      (migration `c1d2e3f4a5b6`); skipped+logged when no local post.
- [x] HMAC `X-Hub-Signature-256` verification (`_verify_signature`,
      constant-time compare). **Gated behind the new
      `meta_verify_webhook_signature` flag (default OFF)** so the Phase
      5e DM mirror keeps its unsigned behaviour — the user's `.env.local`
      sets `META_APP_SECRET`, so a secret-presence trigger would have
      broken the mirror's parity tests. Enable the flag in production.
- [x] Tests: comments/reply/mention/caption-only/story_insights(+no-post)/
      unknown-account at the service layer; bad-sig 401, missing-sig 401,
      valid-sig routes, flag-off skips at the endpoint.

**Test tally:** 84 green (22 models + 24 publisher + 13 router +
14 comments + 11 webhook-changes) — plus the 7 Phase 5e mirror webhook
tests stay green (flag default OFF).

### I.9 — Rate limit + quota awareness ✅

- [x] Pre-publish check via `publisher.fetch_publishing_limit`
      (`GET /{ig-user-id}/content_publishing_limit`). Gated behind the
      new `meta_check_publishing_quota` flag (default OFF so the publish
      path stays one round-trip); when ON + cap reached, the post fails
      `quota_exceeded` before any container create. Best-effort: a
      failed quota call doesn't block publishing.
- [x] `THROTTLE_ERROR_CODES = {4, 17, 80001, 80002}` + `is_throttle_error`.
      `X-App-Usage` + `X-Business-Use-Case-Usage` headers captured into
      the error message (`_usage_note`); throttle failures tagged
      `[rate-limited]` (`_augment_throttle`) at every external-call
      failure point (single + carousel create, publish).
- [x] ARQ task backs off + retries on throttle: `reset_for_retry`
      (failed→pending) + `arq.Retry(defer=900s)` up to
      `THROTTLE_MAX_RETRIES=3`. Non-throttle failures stay terminal.
- [x] Tests: quota parse, quota-exceeded blocks (no create call),
      quota-ok proceeds, quota-error best-effort, throttle message tag
      + usage capture, reset_for_retry.

**Test tally:** 90 green (22 models + 30 publisher + 13 router +
14 comments + 11 webhook-changes). (ARQ Retry mechanics use the
worker's own engine — exercised in prod, not the mock suite, mirroring
the existing immediate-publish worker path.)

### I.10 — Connection flows (OAuth + Instagram Login + manual token) ✅

**Three ways to connect a client's Instagram, because most clients do
NOT have a Facebook Page** (verified May 2026 against Meta docs):

| Flow | FB Page? | Publish | Comments | **Delete media** |
|---|---|---|---|---|
| **Facebook Login** (`graph.facebook.com`) | required | ✅ | ✅ | ✅ |
| **Instagram Login** (`graph.instagram.com`) | not needed (Professional acct only) | ✅ | ✅ | ❌ API-unsupported |
| **Manual / advanced** (paste token) | n/a | ✅ | ✅ | depends on token's login type |

> **Verified:** `DELETE /{ig-media-id}` *"only supports Instagram API
> with Facebook Login"* (Meta docs, instagram-media reference). Instagram
> Login can publish + moderate but cannot delete media via API.

- [ ] Add a `login_type` (`facebook` / `instagram` / `manual`) marker on
      the channel so the app knows each connection's capabilities. The
      I.6 delete endpoint gates on it: non-Facebook-Login channels return
      a clear 422 ("delete unavailable on Instagram Login — remove it
      from the IG app") instead of a confusing Meta `#10`.
- [ ] **Facebook Login flow** (full capabilities):
      * `…/instagram_channels/connect/start` → FB Login dialog w/ scopes.
      * `…/connect/callback` → code → long-lived user token → page token
        (non-expiring) + IG business id → store on the channel.
- [ ] **Instagram Login flow** (no FB Page; lower friction):
      * `…/instagram_channels/connect_ig/start` → IG OAuth dialog.
      * `…/connect_ig/callback` → code → long-lived IG user token →
        store on the channel (host `graph.instagram.com`). Requires the
        publisher/comment clients to accept a per-channel base host.
- [ ] **Manual / advanced mode:** an admin-only endpoint to paste an
      `access_token` + `instagram_id` (+ pick `login_type`) straight onto
      the channel — for System User tokens (permanent, from Business
      Manager), agencies with their own token, and support/debug. Tiny:
      it just writes the two fields the publisher already reads.
- [ ] Tests with respx mocks for each flow's Meta endpoints + the
      delete-capability gate.

**Status — shipped in 4 chunks (all respx-mocked, 25 connect tests):**
- [x] **ig.10a** — `instagram_channel_settings` (login_type) + manual
      connect (paste token) + `can_delete_media` gate on the delete path.
- [x] **ig.10b** — Facebook Login OAuth (signed state, code→long-lived
      page token→IG id, inbox+channel creation), `connect/start` +
      account-less `/api/v1/instagram/oauth/callback`.
- [x] **ig.10c** — Instagram Login OAuth (no FB Page; host
      graph.instagram.com), `connect/start_instagram` + callback
      dispatch by `state.flow`.
- [x] **ig.10d** — per-channel Graph host (task-local contextvar):
      publish + comments route to graph.instagram.com for IG-login
      channels, graph.facebook.com otherwise (default keeps every
      existing call site unchanged).

> **One Meta app, multitenant:** a single AloStudio Meta app (Live +
> App Review / Advanced Access) serves unlimited client accounts — each
> client connects *their* IG to *our* app; they never create their own
> Meta app. Per-IG-account publish quota (100/24h) is independent;
> only the app-level `X-App-Usage` is shared (already captured in I.9).

### I.11 — Product / catalog association (CRM context) ✅

**Why:** clients use AloStudio like a CRM — they keep a catalogue of
products/services and promote them in IG posts + stories. A post (or
story) can be linked to **0, 1 or N products**. When an IG user comments
or DMs about that media, the system resolves *media → post → products* so
an AI agent answers with the right product context.

- [x] New **`products`** table — account-scoped catalogue, generic
      (`app/domains/products/`): `name, description, sku?, price?(numeric),
      currency?, url?, image_url?, enabled`. Index on `account_id`.
- [x] New **`instagram_post_products`** join (M2M) +
      `UNIQUE(post_id, product_id)`. Migration `d2e3f4a5b6c7` (both
      tables); applied to dev + test DBs.
- [x] **Product CRUD** under `/api/v1/accounts/{id}/products`
      (`products_router`, wired in main.py): read = admin OR agent,
      writes = admin only.
- [x] **Link on publish:** `InstagramPostCreate.product_ids: list[int]`;
      `create_post` calls `set_post_products`, which validates the ids
      belong to the account (422 on a foreign/unknown id) and replaces
      the links idempotently. Works for every media type incl. STORIES.
- [x] **Surface:** `present_post` includes `products: [...]` (show +
      create); `GET /instagram_posts/{id}/products`.
- [x] **AI-context resolver:** `products_for_media(account_id,
      ig_media_id)` resolves *media → post → products* — the hook for an
      AI agent / the MCP server when a comment/DM arrives.
- [x] Tests (`test_products.py`): product CRUD (service + endpoints,
      admin-gated, agent blocked), linking + foreign-id 422, both
      resolvers, cascade on post + product delete, create-with-
      product_ids endpoint, unknown-id 422.

**Test tally:** product suite 12 green; full IG+products suite green.

### I.12 — Tests + close branch ✅

- [x] Full end-to-end scenario (`test_instagram_e2e.py`): connect →
      product → create post (+product) → publish → show → media→product
      resolver → comment → hide → delete.
- [x] README section for the new endpoints (`app/domains/instagram/README.md`).
- [ ] Mark branch ready for merge (after I.13).

### I.13 — Instagram MCP tools (added) ✅

Exposes the extension to AI agents via the MCP server (`feat/mcp-server`,
merged into this branch).

- [x] Merged `feat/mcp-server` → `feat/instagram-graph` (conflict-free;
      only `app/mcp/*` + pyproject/uv.lock). Alembic two-heads unified
      by merge migration `f4a5b6c7d8e9` (applied to both DBs).
- [x] `app/mcp/tools/instagram.py` (account-scoped via the bearer token,
      registered in `tools/__init__.py`):
      * read: `list_instagram_posts`, `show_instagram_post`,
        `list_instagram_products`, `instagram_products_for_media`
        (**the AI context hook**), `list_instagram_comments`.
      * write: `create_instagram_post` (schedules; omit `scheduled_for`
        → next tick), `post_instagram_comment`,
        `reply_to_instagram_comment`, `hide_instagram_comment`.
- [x] Tests (`test_mcp_instagram_tools.py`): list, products_for_media,
      scheduled create (+products), reply (respx), read-scope denial.

**Then:** merge `feat/instagram-graph` → `main`.

---

## Known unknowns (from verification)

Items the research couldn't pin down — we'll need to discover during
implementation:

1. **Per-user hourly call ceiling** — Meta docs say it exists but
   don't publish the number. We'll detect via `X-App-Usage`.
2. **`/blocked_users` edge** — Phase 5e+I.7 ships *hide*; account-
   level user blocks remain UI-only (no API).
3. **Mixed-content carousel behavior** — docs say ≤10 children but
   don't pin behavior when mixing reels + images. We'll test in
   sandbox.
4. **`audio_name` retry error code** — write-once-only on Reels but
   the error code for a 2nd attempt isn't documented.
5. **`trial_params` Reels graduation** — listed as a param but the
   state machine isn't published. Defer until needed.

---

## Commit style

`ig.<n>: <area>: <short summary>` — one commit per milestone.

## Tracking

### Real-Meta validation (done)

- [x] **Publish path validated against the live Graph API** via
      `scripts/ig_publish_smoke.py` — create container → poll →
      `media_publish` → permalink + quota all succeed on the test
      account (post `DYlgwWiDoyC`, IG business id `17841451736515320`).
- [~] **Delete** reached Meta but returned `#10 insufficient permissions`
      with the test token — code is correct (parsed the error + captured
      `X-App-Usage`); needs the delete scope / App Review on Meta's side.
- See `MANUAL-instagram-credenciales.md` for obtaining a non-expiring
  Page token.

Token rotation + Meta App setup checklist (user-side, outside this
repo):

- [ ] Rotate the leaked test token via Developer Dashboard.
- [x] Confirm test IG Business Account is linked to a test FB Page.
- [ ] Confirm app review status: dev mode is fine for testing; for
      production we'll need `instagram_content_publish` reviewed.
- [x] Get `META_APP_ID` + `META_APP_SECRET` from Dashboard.
