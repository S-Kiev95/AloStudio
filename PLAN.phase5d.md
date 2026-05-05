# Phase 5d — Channel: Facebook Messenger

**Why this phase:** Facebook is a sibling of WhatsApp Cloud — same
Meta Graph API, same webhook handshake pattern, but a different
data shape and a per-app (not per-channel) verify token. Porting it
right after 5c lets us reuse most of the infrastructure.

**Reference anchors (verbatim paths under `reference/chatwoot/`):**

* `app/models/channel/facebook_page.rb`
* `app/builders/messages/facebook/message_builder.rb`
* `app/jobs/webhooks/facebook_events_job.rb`
* `app/jobs/webhooks/facebook_delivery_job.rb`
* `app/services/facebook/send_on_facebook_service.rb`
* `config/initializers/facebook_messenger.rb`
  (`ChatwootFbProvider#valid_verify_token?` — global env-var lookup)

---

## Scope decision: text in/out + Graph send

Same shape as 5c (Cloud) but smaller because Facebook's surface is
mostly subsumed by WhatsApp's:

  * **Channel model**: `channel_facebook_pages` (page_id +
    page_access_token + user_access_token + instagram_id).
  * **Webhook**: shared verify-token handshake using a global app-level
    env var (`FB_VERIFY_TOKEN`). Messenger payload differs from
    WhatsApp Cloud — `entry[].messaging[]` instead of
    `entry[].changes[].value.messages[]`.
  * **Inbound**: text messages only in 5d.
  * **Outbound**: `POST /me/messages?access_token=<page>` with
    `recipient.id` + `message.text` + `messaging_type=RESPONSE`.

## Test strategy: respx (same as 5c)

No fake server needed — `respx` already handles Graph mocking.
The Messenger payload shapes are documented + tested against the
Chatwoot rspec fixtures in `spec/services/facebook/`.

---

## Milestones

### 5d.1 — FacebookPage channel model + migration + InboxBuilder branch + verify-token setting

**Tasks:**
- [ ] `app/domains/inboxes/models.py::FacebookPage` —
      `channel_facebook_pages` table mirroring Chatwoot's schema
      (page_id, page_access_token, user_access_token, instagram_id).
- [ ] Alembic migration with the unique
      `(page_id, account_id)` index.
- [ ] Add `CHANNEL_TYPE_FACEBOOK = 'Channel::FacebookPage'` constant.
- [ ] InboxBuilder ``facebook`` branch validating `page_id` +
      `page_access_token`.
- [ ] Add `fb_verify_token` setting to :class:`Settings` —
      a global app-level token. The agent provisions Meta's webhook
      with this value (matches Rails' `FB_VERIFY_TOKEN` env var).
- [ ] Tests: builder happy path + uniqueness constraint.

### 5d.2 — Webhook receiver + Meta verification handshake

Mirrors 5c.2 but uses the global `fb_verify_token` setting instead
of per-channel `provider_config['webhook_verify_token']`.

**Tasks:**
- [ ] `app/domains/facebook/router.py` — endpoints:
        - `GET  /webhooks/fb_messenger` — verify handshake.
        - `POST /webhooks/fb_messenger` — receives the payload,
          dispatches per-page to the inbound processor.
- [ ] No phone-number-style 404 — Facebook's webhook path is fixed,
      and the page_id lives inside the payload (`entry[].id`).
      Unknown page_ids drop silently, matching the 5c receive flow.
- [ ] Tests: 401 on bad verify_token, 200 + challenge echo on good,
      200 ack on POST.

### 5d.3 — FB Messenger inbound processor (text)

Walk the Messenger payload + create rows.

**Tasks:**
- [ ] `app/domains/facebook/incoming.py` —
      `process_facebook_webhook(session, payload) -> list[Message]`.
      Walks `entry[].messaging[]`, resolves the FB page by `entry.id`,
      creates / re-uses Contact (source_id = sender PSID), creates /
      re-uses Conversation, inserts incoming Message stamped with the
      Messenger `message.mid`.
- [ ] Idempotent on `mid` via `messages.source_id` lookup.
- [ ] Tests against fixtures lifted from Chatwoot's rspec specs.

### 5d.4 — FB outbound (send_message via Graph API)

**Tasks:**
- [ ] `app/domains/facebook/sender.py` —
      `send_text_message_facebook(session, channel, message,
      to_psid)`. POSTs `{recipient: {id}, message: {text},
      messaging_type: 'RESPONSE'}` to
      `https://graph.facebook.com/v17.0/me/messages?access_token=<page>`.
- [ ] Stamps the returned `message_id` on `messages.source_id`.
- [ ] Hooks into `_apply_message_post_create` like the WhatsApp +
      email senders.
- [ ] Tests: respx mocks Graph; assert URL/body/header shape.

### 5d.5 — Parity tests + close 5d

- [ ] Cross-backend 401/200 envelope assertions on the FB webhook.
- [ ] Update `PLAN.md` to mark 5d done.

---

## Deferred

* **OAuth flow** — connecting a Facebook page (the `/auth/facebook`
  callback that exchanges the user code for a page_access_token)
  lands with the Phase 9 OAuth bundle. Until then the agent supplies
  the token directly to InboxBuilder.
* **Attachments** (image/video/file/sticker/location) — needs Phase
  10 storage.
* **Echoes** (`outgoing_echo` — when a page admin replies via the FB
  Messenger app, Meta echoes the message back to our webhook).
* **Standby + handover protocol** — multi-app routing (rare).
* **Postback / quick_reply / get_started events** — bot infrastructure,
  Phase 8.
* **Reauthorization** (token rotation) — Phase 9.
* **Webhook subscription setup** (Meta API call to subscribe the page
  to specific webhook fields) — currently auto-fired in Rails on
  channel create. We defer + leave a manual setup in the deployment
  README.

---

## Commit style

`phase5d: <area>: <short summary>` — one commit per milestone.
