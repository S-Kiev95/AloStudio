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

- [ ] `instagram_posts`, `instagram_post_containers`,
      `instagram_comments` tables + Alembic migration.
- [ ] SQLModel classes.
- [ ] Service skeleton (no business logic yet): create_post,
      list_posts, get_post, delete_post.
- [ ] Tests: model round-trip + cascade deletes.

### I.2 — Single image publish

- [ ] `app/domains/instagram/publisher.py` — POST `/media` for
      single image with full param support.
- [ ] `app/domains/instagram/poller.py` — status_code polling helper
      with Meta's 1-min cadence + 5-attempt cap.
- [ ] ARQ task `publish_instagram_post` for the happy path.
- [ ] HTTP endpoint `POST /api/v1/accounts/{id}/instagram_posts`.
- [ ] respx-mocked tests covering full state machine
      (pending → publishing → published).

### I.3 — Video + Reels publishing

- [ ] Extend publisher to handle `media_type=VIDEO`/`REELS`.
- [ ] Polling path actually exercised (videos take longer than the
      test sandbox; we mock).
- [ ] Reels-specific params (cover_url, share_to_feed, audio_name).
- [ ] Tests for each variant + the `ERROR` / `EXPIRED` paths.

### I.4 — Carousel publishing

- [ ] Carousel parent + children orchestration in ARQ task.
- [ ] Children polled in parallel; parent only created when all are
      FINISHED.
- [ ] ≤10 children enforced server-side (422 otherwise).
- [ ] Tests for mixed image+video carousel.

### I.5 — Stories

- [ ] `media_type=STORIES` branch + 24h auto-expiry handling
      (no manual delete needed; row stays for audit).
- [ ] Tests.

### I.6 — Delete media

- [ ] `DELETE /api/v1/accounts/{id}/instagram_posts/{id}` →
      `DELETE /{ig-media-id}` on Meta + update local row state to
      ``deleted``.
- [ ] Tests for the documented restrictions (carousel children can't
      be individually deleted; live video can't be deleted).

### I.7 — Comments — read + write + moderation

- [ ] List comments on a media (with `replies{...}` expansion).
- [ ] Post comment / reply.
- [ ] Hide (toggle) / delete.
- [ ] CRUD endpoints + service tests.

### I.8 — Webhook receiver for comments + mentions + story_insights

- [ ] Extend Phase 5e's existing `/webhooks/instagram` handler to
      route `comments` / `mentions` / `story_insights` fields.
- [ ] `comments` event creates an `instagram_comments` row + optionally
      a `Conversation` if the comment is on a post we want to surface
      in the inbox (account-config flag).
- [ ] `mentions` creates a similar entry.
- [ ] `story_insights` stamps the row's metrics for analytics.
- [ ] HMAC `X-Hub-Signature-256` verification using the existing
      app_secret env var.

### I.9 — Rate limit + quota awareness

- [ ] Pre-publish check via `GET /{ig-user-id}/content_publishing_limit`.
- [ ] Detect `X-App-Usage` + `X-Business-Use-Case-Usage` headers;
      stamp into `instagram_posts.error_message` on throttle (codes
      4, 17, 80001, 80002).
- [ ] ARQ task backs off + retries on throttle errors.

### I.10 — OAuth flow

- [ ] `/api/v1/accounts/{id}/instagram_channels/connect/start` —
      redirect to FB Login dialog with all scopes.
- [ ] `/api/v1/accounts/{id}/instagram_channels/connect/callback` —
      code exchange → long-lived user token → page tokens → store
      Page token on `InstagramChannel.access_token`.
- [ ] Tests with respx mocks for Meta's OAuth endpoints.

### I.11 — Tests + close branch

- [ ] Full end-to-end scenario: create post → poll → publish → comment
      → moderate → delete.
- [ ] README section for the new endpoints.
- [ ] Mark branch ready for merge.

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

Token rotation + Meta App setup checklist (user-side, outside this
repo):

- [ ] Rotate the leaked test token via Developer Dashboard.
- [ ] Confirm test IG Business Account is linked to a test FB Page.
- [ ] Confirm app review status: dev mode is fine for testing; for
      production we'll need `instagram_content_publish` reviewed.
- [ ] Get `META_APP_ID` + `META_APP_SECRET` from Dashboard.
