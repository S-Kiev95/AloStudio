# Phase 5e — Channel: Instagram DM

**Why this phase:** Instagram DMs share Meta's Graph API with
Facebook Messenger, so most of 5d carries over. The differences are
the channel model (separate ``channel_instagram`` table for the
"Direct Instagram Login" path), the webhook URL (``/webhooks/instagram``),
and a slightly different webhook payload shape (the ``entry.id``
identifies an Instagram account, not a FB page).

**Reference anchors (verbatim paths under `reference/chatwoot/`):**

* `app/models/channel/instagram.rb`
* `app/controllers/webhooks/instagram_controller.rb`
* `app/jobs/webhooks/instagram_events_job.rb`
* `app/services/instagram/messenger/send_on_instagram_service.rb`

---

## Scope decision: Direct IG Login first, FB-page IG later

Chatwoot supports TWO Instagram routings:

1. **Direct Instagram Login** (`Channel::Instagram`) — the modern
   path. Standalone channel row with its own ``access_token`` +
   ``instagram_id``. Set up via Meta's Instagram Business app.
2. **Instagram via Facebook Page** (`Channel::FacebookPage` with
   ``instagram_id`` set) — legacy. The FB page acts as the proxy
   for IG DMs.

We port **(1)** in 5e. The legacy FB-page path is deferred to a later
sub-phase: it requires routing webhooks based on whether the IG id
resolves to an IG channel OR an FB page row, plus a separate signing
key for outbound. The straight IG path covers >95% of real
deployments.

## Test strategy: respx (same as 5d)

Inbound parser is mostly identical to FB Messenger — shared payload
shape (``entry[].messaging[]``). Outbound posts to the same Graph
endpoint with a different access token. Reuse the FB sender's
URL-pattern with channel-specific tweaks.

---

## Milestones

### 5e.1 — InstagramChannel model + migration + InboxBuilder + verify-token setting

**Tasks:**
- [ ] `app/domains/inboxes/models.py::InstagramChannel` —
      ``channel_instagram`` table mirroring Chatwoot v4.13.0
      (instagram_id + access_token + expires_at).
- [ ] Alembic migration with the unique ``instagram_id`` index.
- [ ] Add `CHANNEL_TYPE_INSTAGRAM = 'Channel::Instagram'` constant.
- [ ] InboxBuilder ``instagram`` branch validating ``instagram_id``
      + ``access_token``.
- [ ] Add `ig_verify_token` setting (Chatwoot uses both
      ``IG_VERIFY_TOKEN`` and ``INSTAGRAM_VERIFY_TOKEN``; we ship
      one canonical name and accept it everywhere).
- [ ] Tests: builder happy path + uniqueness constraint.

### 5e.2 — Webhook receiver + Meta verification handshake

Mirrors 5d.2 but mounted at ``/webhooks/instagram`` and reads the
IG verify token instead of the FB one. The body parser also gates
on ``object == 'instagram'`` (matches Rails'
``params['object'].casecmp('instagram').zero?``).

**Tasks:**
- [ ] `app/domains/instagram/router.py` — endpoints:
        - `GET  /webhooks/instagram` — verify handshake.
        - `POST /webhooks/instagram` — accepts payload, dispatches
          to the inbound processor.
- [ ] Body with ``object != 'instagram'`` returns 422 (Rails uses
      `head :unprocessable_entity`).
- [ ] Tests: 401 on bad token, 200 + challenge echo on good, 200
      on POST.

### 5e.3 — Instagram inbound processor

Walk Meta's IG webhook payload, create rows. Shape matches FB but
the page id is the IG account id and contacts are identified by IG
USER_ID (similar to PSID).

**Tasks:**
- [ ] `app/domains/instagram/incoming.py` —
      ``process_instagram_webhook(session, payload)``.
- [ ] Idempotent on ``mid`` via ``messages.source_id``.
- [ ] Echoes (``message.is_echo``) handled the same way as 5d.3.
- [ ] Tests against canonical IG payloads.

### 5e.4 — Instagram outbound (send_message via Graph API)

**Tasks:**
- [ ] `app/domains/instagram/sender.py` —
      ``send_text_message_instagram``. POSTs to
      ``graph.facebook.com/<vN>/me/messages?access_token=<channel>``
      with ``recipient.id`` + ``message.text``.
- [ ] Stamps Meta's ``message_id`` on ``messages.source_id``.
- [ ] Hooks into ``_apply_message_post_create``.
- [ ] Tests: respx mocks Graph; assert URL/body.

### 5e.5 — Parity tests + close 5e

- [ ] Cross-backend assertions on the IG webhook auth gate.
- [ ] Update `PLAN.md` to mark 5e done.

---

## Deferred

* **Instagram via Facebook Page** (legacy path on
  ``Channel::FacebookPage.instagram_id``) — needs payload-routing
  logic that dispatches to either the IG channel or the FB page
  channel. Sub-phase 5e.6 / Phase 9.
* **`appsecret_proof` HMAC signing** on outbound — Phase 9 hardening.
* **Attachments** — Phase 10 storage.
* **Stories / story_replies** — niche.
* **Reactions / read events** — same as Messenger, port if needed
  during 5e.3 if the test suite demands it.
* **OAuth flow** to obtain the access_token + instagram_id —
  Phase 9 OAuth bundle.
* **Reauthorization** when the access_token expires — Phase 9.

---

## Commit style

`phase5e: <area>: <short summary>` — one commit per milestone.
