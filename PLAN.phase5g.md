# Phase 5g — Channel: Telegram

**Why this phase:** Telegram closes the channel cluster. Simpler
than Meta's surfaces — single bot token, no verify-token handshake
(the secret token sits in the webhook URL itself), one Graph-style
JSON API.

**Reference anchors (verbatim paths under `reference/chatwoot/`):**

* `app/models/channel/telegram.rb`
* `app/services/telegram/incoming_message_service.rb`
* `app/services/telegram/param_helpers.rb`
* `app/services/telegram/send_on_telegram_service.rb`
* `app/controllers/webhooks/telegram_controller.rb`
* `app/jobs/webhooks/telegram_events_job.rb`

---

## Scope decision

The webhook URL contains the bot_token (``/webhooks/telegram/<bot_token>``)
— Telegram requires this so the bot can verify the request actually
came from Telegram (anyone hitting the URL must already know the
secret token, which we treat as auth). No separate verify handshake.

Send goes through ``api.telegram.org/bot<token>/sendMessage`` — the
token lives in the URL again, no HTTP auth header.

5g.1-5g.4 ship:
  * Channel model + InboxBuilder.
  * Webhook receiver + inbound processor (text only, private chats
    only — Chatwoot intentionally drops group chats).
  * Outbound text via Telegram Bot API.
  * Parity tests + PLAN update.

Deferred to follow-ups:
  * Business chat mode (``business_connection_id`` set) — Phase 9
    once Telegram Business adoption stabilises.
  * Callback queries (inline-button replies).
  * Attachments / media (photo, document, voice, video) — Phase 10.
  * Profile-photo sync via ``getUserProfilePhotos``.
  * Webhook validation via ``setWebhook`` on inbox create —
    requires a public-facing URL the test environment doesn't have.
    Phase 9 deployment hardening.
  * Edit messages (``editMessageText`` via update_message_service).

## Test strategy: respx (same as 5d-5f)

Telegram's API is a vanilla JSON HTTP service. respx intercepts
httpx so no real Bot API call ever fires.

---

## Milestones

### 5g.1 — TelegramChannel model + migration + InboxBuilder branch

**Tasks:**
- [ ] `TelegramChannel` SQLModel — ``channel_telegram`` with
      bot_token UNIQUE + bot_name (read from Telegram's getMe;
      InboxBuilder accepts a caller-supplied value rather than
      calling Telegram on create — defer the live validation).
- [ ] Alembic migration with the unique bot_token index.
- [ ] Add `CHANNEL_TYPE_TELEGRAM = 'Channel::Telegram'`.
- [ ] InboxBuilder ``telegram`` branch validating bot_token (and
      defaulting bot_name to ``"telegram-bot"`` if not supplied).
- [ ] Tests: builder happy path + uniqueness.

### 5g.2 — Webhook receiver + inbound processor

**Tasks:**
- [ ] `app/domains/telegram/router.py` —
        ``POST /webhooks/telegram/{bot_token}``.
- [ ] `app/domains/telegram/incoming.py` —
        ``process_telegram_webhook(session, *, bot_token, payload)``.
        Resolves channel by bot_token, walks message, creates
        Contact + ContactInbox keyed by ``from.id`` + Conversation
        with chat_id stamped in additional_attributes.
- [ ] Idempotent on Telegram's ``message_id``.
- [ ] Group chats dropped — only ``message.chat.type=='private'``
        proceeds.
- [ ] Tests against canonical Telegram payloads.

### 5g.3 — Outbound

**Tasks:**
- [ ] `app/domains/telegram/sender.py` —
        ``send_text_telegram(session, channel, message, chat_id)``.
        POSTs ``{chat_id, text}`` (and optional
        ``reply_to_message_id`` from
        ``content_attributes.in_reply_to_external_id``) to
        ``api.telegram.org/bot<token>/sendMessage``.
- [ ] Stamps Telegram's returned ``message_id`` on
        ``messages.source_id``.
- [ ] Hooks into ``_apply_message_post_create``.
- [ ] Tests via respx.

### 5g.4 — Parity tests + close 5g

- [ ] Cross-backend assertions on the webhook 200-ack invariant.
- [ ] Update `PLAN.md` to mark 5g done.

---

## Commit style

`phase5g: <area>: <short summary>` — one commit per milestone.
