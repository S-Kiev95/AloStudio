# Instagram extension

Own-extension (outside the Chatwoot mirror) on top of the Phase 5e
`channel_instagram` row: **publishing, comment moderation, webhook
reception, a product catalogue link, and connection flows**.

All Meta calls are respx-mocked in tests; the publish path is also
validated against the live Graph API (`scripts/ig_publish_smoke.py`).

- Verified API spec + design: [`PLAN.instagram-graph.md`](../../../PLAN.instagram-graph.md)
- Getting permanent credentials: [`MANUAL-instagram-credenciales.md`](../../../MANUAL-instagram-credenciales.md)

---

## Capabilities by connection type

| Connection (`login_type`) | FB Page? | Publish | Comments | Delete media |
|---|---|---|---|---|
| **Facebook Login** (`facebook`) | required | ✅ | ✅ | ✅ |
| **Instagram Login** (`instagram`) | no | ✅ | ✅ | ❌ (Meta API limitation) |

`login_type` lives on `instagram_channel_settings` and selects the Graph
host per channel (`graph.facebook.com` vs `graph.instagram.com`). The
delete endpoint 422s on Instagram-Login channels.

## Media types & scheduling

`IMAGE`, `VIDEO`, `REELS`, `CAROUSEL` (≤10 children), `STORIES`.
`scheduled_for`: null → publish now; future → queued (5-min scheduler
fires it); past → 422. No upper bound. Stories publish flat media only
(no native stickers/text — pre-render those into the media).

---

## Endpoints (all admin-only unless noted)

### Publishing — `…/api/v1/accounts/{id}/instagram_posts`
| Method | Path | Notes |
|---|---|---|
| GET | `` | list (filter `state`, `page`) |
| POST | `` | create; body `{inbox_id, media_type, source, caption?, scheduled_for?, product_ids?}` |
| GET | `/{post_id}` | show (+ containers + products) |
| DELETE | `/{post_id}` | delete on Meta + flip to `deleted` (FB Login only) |
| GET | `/{post_id}/products` | linked catalogue products (AI/CRM context) |

`source` per media type: IMAGE `{image_url}` · VIDEO/REELS
`{video_url, cover_url?, thumb_offset?, share_to_feed?}` · CAROUSEL
`{children:[{image_url|video_url}, …]}` · STORIES `{image_url|video_url}`.

### Comments — moderation
| Method | Path |
|---|---|
| GET | `…/instagram_posts/{post_id}/comments` (live sync from Meta) |
| POST | `…/instagram_posts/{post_id}/comments` `{message}` |
| POST | `…/instagram_comments/{comment_id}/replies` `{message}` |
| POST | `…/instagram_comments/{comment_id}/hide` `{hide}` |
| DELETE | `…/instagram_comments/{comment_id}` |

### Connection — `…/api/v1/accounts/{id}/instagram_channels`
| Method | Path | Notes |
|---|---|---|
| POST | `/connect_manual` | paste a token `{name, instagram_id, access_token, login_type, expires_at?}` |
| GET | `/connect/start` | Facebook Login dialog URL (signed state) |
| GET | `/connect/start_instagram` | Instagram Login dialog URL |
| GET | `/{channel_id}/settings` | capabilities (`login_type`, `can_delete_media`) |
| GET | `/api/v1/instagram/oauth/callback` | account-less OAuth callback (state-authed) |

### Products — `…/api/v1/accounts/{id}/products`
CRUD (`name, description?, sku?, price?, currency?, url?, image_url?,
enabled`). Read = admin OR agent; writes = admin. Link to posts via
`product_ids` on create; resolve `media → post → products` with
`publishing_service.products_for_media(...)` (the AI-context hook).

### Webhook — `/webhooks/instagram`
`GET` verify handshake (`ig_verify_token`). `POST` receives events:
DMs (Phase 5e) + `comments` / `mentions` / `story_insights` (this
extension). Optional `X-Hub-Signature-256` HMAC behind
`META_VERIFY_WEBHOOK_SIGNATURE`.

---

## Environment

| Var | For |
|---|---|
| `META_APP_ID` / `META_APP_SECRET` | Facebook Login OAuth + webhook HMAC |
| `META_INSTAGRAM_APP_ID` / `META_INSTAGRAM_APP_SECRET` | Instagram Login OAuth |
| `META_OAUTH_REDIRECT_URI` | OAuth callback (must match the Meta app) |
| `META_GRAPH_API_VERSION` | pinned `v23.0` |
| `META_VERIFY_WEBHOOK_SIGNATURE` | enforce webhook HMAC (default off) |
| `META_CHECK_PUBLISHING_QUOTA` | pre-publish 24h quota check (default off) |

The per-account Page token + IG id live on the channel row, never in env.

---

## Module map

| File | Role |
|---|---|
| `models.py` | posts, containers, comments, products join, channel settings |
| `publishing_service.py` | state machine, products, comments, delete |
| `publisher.py` / `poller.py` | Graph publish + container polling |
| `comments_client.py` | comment edges |
| `oauth.py` / `connect_service.py` | FB + IG Login token exchange, signed state |
| `graph.py` | per-channel Graph host (contextvar) |
| `webhook_changes.py` | comments/mentions/story_insights receiver |
| `*_router.py` | publishing, comments, connect endpoints |

## MCP tools (I.13)

After merging `feat/mcp-server`, these operations are exposed to AI
agents as MCP tools (`app/mcp/tools/instagram.py`, account-scoped via
the bearer token):

| Tool | Scope | Purpose |
|---|---|---|
| `list_instagram_posts` | read | list posts (filter `state`) |
| `show_instagram_post` | read | post + containers + products |
| `list_instagram_products` | read | the catalogue |
| `instagram_products_for_media` | read | **AI hook** — media → product(s) |
| `list_instagram_comments` | read | local comment mirror for a media |
| `create_instagram_post` | write | schedule/queue a post (+`product_ids`) |
| `post_instagram_comment` | write | comment on a published post |
| `reply_to_instagram_comment` | write | reply to a comment |
| `hide_instagram_comment` | write | hide/unhide (moderation) |

The headline is `instagram_products_for_media`: when an IG user comments
or DMs about a post, the agent resolves the product(s) it promotes and
answers with the right context.
