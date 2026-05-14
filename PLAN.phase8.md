# Phase 8 — Integrations

**Why this phase:** Outgoing event emitters (webhooks + agent bot
relays) close the loop between Chatwoot and the rest of the world.
This is also where the deferred ``AgentBot`` infra from earlier
phases finally lands — letting Phase 7's ``bot_resolutions_count`` /
``bot_handoffs_count`` start producing non-zero values.

**Reference anchors (verbatim paths under `reference/chatwoot/`):**

* `app/models/agent_bot.rb`
* `app/models/agent_bot_inbox.rb`
* `app/models/webhook.rb`
* `app/models/integrations.rb` + `app/models/integrations/*`
* `app/controllers/api/v1/accounts/agent_bots_controller.rb`
* `app/controllers/api/v1/accounts/webhooks_controller.rb`
* `app/controllers/api/v1/accounts/integrations/{slack,hooks}_controller.rb`
* `app/listeners/{webhook_listener,agent_bot_listener}.rb`
* `app/builders/webhook_builder.rb`

---

## Scope decisions

Chatwoot's Phase 8 surface ranges from generic (webhooks) to vendor-
specific (Slack, Dialogflow, OpenAI, Shopify, Linear, Dyte, Captain).
We ship the **generic infrastructure** that every integration relies
on and **defer per-vendor adapters** to dedicated follow-up phases.

**In scope:**
  * ``AgentBot`` model + CRUD + ``AgentBotInbox`` join — completes
    the bot-side of conversation lifecycle that was stubbed in 4b
    (assignee_agent_bot_id) and 7 (bot_resolutions_count).
  * Outbound bot relay — when an ``input_*`` or text message is
    created on an inbox with an attached bot, POST to the bot's
    ``outgoing_url`` with the standard Chatwoot webhook payload.
  * ``Webhook`` model + CRUD — user-configured HTTP receivers for
    dispatcher events the account subscribes to.
  * Webhook delivery listener — for each subscribed event the
    listener POSTs the standard envelope to every matching webhook.
  * ``Integrations::Hook`` model + CRUD — the polymorphic registry
    that backs vendor integrations (Slack/Dialogflow/etc).
  * Integration ``apps`` index endpoint — the catalogue surface the
    dashboard's "Integrations" tab consumes.

**Deferred (per-vendor adapters, logged but not implemented):**
  * **Slack** outbound message threading + thread reply ingestion —
    needs actual Slack workspace + OAuth flow. Phase 8 follow-up.
  * **Dialogflow** intent routing — agent_bot rides on top, vendor
    config defers.
  * **OpenAI** / **Captain** — Captain is enterprise-only; OpenAI
    Q&A reply suggestion ships post-8.
  * **Shopify / Linear / Dyte / Stripe / Firecrawl** — vendor SDKs,
    each their own follow-up.
  * **Twitter / LINE / TikTok** channel-style webhooks — channel
    surfaces, slot in alongside the 5x channel cluster when needed.
  * Webhook ``inbox_type`` scoping (subscriptions per inbox) — ships
    when the dashboard needs to drive it; not parity-critical now.

## Test strategy

  * **Integration** — model CRUD + listener emits the right POST body
    via ``respx`` (same pattern as the channel outbound tests).
  * **Parity** — stateless 401 envelopes per surface.

---

## Milestones

### 8.1 — AgentBot CRUD + AgentBotInbox link

**Tasks:**
- [ ] `AgentBot` SQLModel + Alembic migration
      (id, account_id, name, description, outgoing_url, bot_type,
      bot_config JSONB, secret).
- [ ] `AgentBotInbox` SQLModel + migration
      (agent_bot_id, inbox_id, status).
- [ ] CRUD endpoints `/api/v1/accounts/{id}/agent_bots`
      (admin-only).
- [ ] Inbox attach/detach endpoints:
      `POST /api/v1/accounts/{id}/inboxes/{iid}/set_agent_bot`
      `DELETE /api/v1/accounts/{id}/inboxes/{iid}/set_agent_bot`
      Mirrors Chatwoot's ``inboxes/set_agent_bot`` member action.
- [ ] Tests: CRUD + attach/detach happy paths + auth gates.

### 8.2 — AgentBot listener (outbound POST on message_created)

**Tasks:**
- [ ] Listener subscribes to ``message.created`` and POSTs to the
      attached bot's ``outgoing_url`` with the canonical Chatwoot
      payload (``event: 'message_created'`` + message + conversation +
      contact + inbox).
- [ ] Skip when the conversation has no bot attached, or the message
      is a private note, or the bot has no ``outgoing_url``.
- [ ] HMAC signature: ``X-Chatwoot-Signature`` header = SHA-256 HMAC
      of body bytes with ``bot.secret``.
- [ ] respx-mocked tests for body shape + signature + skip conditions.

### 8.3 — Webhook CRUD + delivery listener

**Tasks:**
- [ ] `Webhook` SQLModel + Alembic migration
      (id, account_id, inbox_id (nullable), name, url, secret,
      webhook_type, subscriptions JSONB).
- [ ] CRUD endpoints `/api/v1/accounts/{id}/webhooks` (admin-only).
- [ ] Validation: URL format (http/https), subscriptions must be a
      non-empty subset of the allowed events list.
- [ ] Listener subscribes to ALL events in the allowed list; for
      each event, POSTs to every Webhook whose ``subscriptions``
      includes the event name.
- [ ] respx-mocked delivery tests.

### 8.4 — Integration hooks scaffold

**Tasks:**
- [ ] `IntegrationsHook` SQLModel + Alembic migration
      (id, account_id, app_id, hook_type, status, settings JSONB,
      reference_id, access_token, inbox_id (nullable)).
- [ ] CRUD endpoints `/api/v1/accounts/{id}/integrations/hooks`
      (admin-only).
- [ ] `GET /api/v1/accounts/{id}/integrations/apps` — static
      catalogue listing the available integration apps. Mirrors
      Chatwoot's ``Integration::App.find_all``.
- [ ] Per-vendor adapters deferred — the model + CRUD are what
      dashboards need to render the "Integrations" tab.

### 8.5 — Parity tests + close Phase 8

- [ ] Stateless 401 parity on every endpoint surface added.
- [ ] Update `PLAN.md` to mark Phase 8 done.

---

## Commit style

`phase8.<n>: integrations: <short summary>` — one commit per milestone.
