# Phase 5c — Channel: WhatsApp Cloud API + 360dialog

**Why this phase:** WhatsApp is the highest-volume channel in most
LATAM/EMEA Chatwoot deployments. Phase 5c gets text-message
round-trip working — templates and embedded signup land in 5c+
follow-ups.

**Reference anchors (verbatim paths under `reference/chatwoot/`):**

* `app/models/channel/whatsapp.rb`
* `app/services/whatsapp/providers/{base,whatsapp_cloud,whatsapp_360_dialog}_service.rb`
* `app/services/whatsapp/incoming_message_*service.rb`
* `app/controllers/webhooks/whatsapp_controller.rb`
* `app/jobs/webhooks/whatsapp_events_job.rb`

---

## Scope decision: Cloud first, 360dialog second, Twilio in its own channel

Chatwoot's `Channel::Whatsapp` supports two providers — `whatsapp_cloud`
(Meta's official Graph API) and `default` (360dialog BSP). Twilio's
WhatsApp lives in `Channel::TwilioSms` so it's a separate phase
(5c-twilio or rolled into 5f's SMS port).

We port **Cloud first** (most common) then 360dialog (similar shape,
different auth/URLs). They share the channel row + the webhook
endpoint — only the outbound provider service + the inbound parser
differ.

## Test strategy: respx mocks the Graph API

WhatsApp doesn't have a Greenmail equivalent. The Graph API lives at
`graph.facebook.com` and any local fake is a non-trivial rebuild.
**`respx`** (already in deps from earlier phases) intercepts httpx
calls so we can:

* Assert the right Graph URL + body get POSTed for outbound.
* Inject Graph 200/4xx/5xx responses without network.
* Replay a real Meta webhook payload against our parser.

Outbound transport is async via `httpx.AsyncClient`. Webhook ingest
is purely a payload parser — no outgoing HTTP, no mock needed.

---

## Milestones

### 5c.1 — WhatsApp channel model + migration + InboxBuilder branch

**Tasks:**
- [ ] `app/domains/inboxes/models.py::WhatsappChannel` —
      `channel_whatsapp` table mirroring Chatwoot's schema
      (phone_number, provider, provider_config JSONB,
      message_templates JSONB).
- [ ] Alembic migration creating the table + the unique index on
      `phone_number`.
- [ ] Add `CHANNEL_TYPE_WHATSAPP = 'Channel::Whatsapp'` constant.
- [ ] InboxBuilder ``whatsapp`` branch validating the per-provider
      provider_config:
        - `whatsapp_cloud` -> requires `api_key`, `phone_number_id`,
          `business_account_id`.
        - `default` (360dialog) -> requires `api_key`, `url`.
- [ ] `webhook_verify_token` is auto-generated at create time
      (Chatwoot calls this from a `before_validation` hook).
- [ ] Tests: builder happy path for both providers + validation matrix.

### 5c.2 — Webhook receiver + Meta verification handshake

Meta sends a GET request with `hub.challenge` + `hub.verify_token`
on subscription setup; we echo back the challenge if the token
matches. Subsequent inbound messages arrive as POSTs.

**Tasks:**
- [ ] `app/domains/whatsapp/router.py` — endpoints:
        - `GET  /webhooks/whatsapp/{phone_number}` — verification
          challenge (echo `hub.challenge` if `hub.verify_token`
          matches the channel's stored token).
        - `POST /webhooks/whatsapp/{phone_number}` — accepts the
          payload, stamps it onto the dispatcher (or a queue for
          5c.3 to consume).
- [ ] Inactive-number guard (mirrors Rails — drop with 422 if the
      number is in the inactive-list).
- [ ] Tests: 403 on bad verify_token, 200 + challenge echo on good,
      404 for unknown phone_number.

### 5c.3 — Cloud incoming-message service

Parse the Meta webhook payload + create Contact + ContactInbox +
Conversation + Message rows.

**Tasks:**
- [ ] `app/domains/whatsapp/incoming_cloud.py` —
      `process_cloud_webhook(payload, channel) -> list[Message]`.
      Payload shape: `{entry: [{changes: [{value: {messages: [...]}}]}]}`.
- [ ] Handle text + interactive replies first; attachments + reactions
      defer to 5c.6 alongside the media-download infrastructure.
- [ ] Idempotent on Meta's `message_id` field (stamp on
      `messages.source_id`).
- [ ] Tests against fixtures captured from real Meta webhooks
      (the Chatwoot rspec specs are a good source — they ship one
      per message type).

### 5c.4 — Cloud outbound — send_message

Send text messages to Meta's Graph API. Templates + media land in
5c.6.

**Tasks:**
- [ ] `app/domains/whatsapp/cloud_provider.py` —
      `send_text_message(channel, message)` POSTing to
      `graph.facebook.com/{phone_number_id}/messages`.
- [ ] Bearer auth via `provider_config['api_key']`.
- [ ] Stamp Meta's response `messages[0].id` on
      `messages.source_id` so threading works.
- [ ] Hooked from `_apply_message_post_create` like the email mailer.
- [ ] Tests: respx asserts the POST shape + injects a 200 response.

### 5c.5 — Tests + parity + close 5c

- [ ] Parity tests for the webhook auth-gates (mirror 5b style).
- [ ] Update `PLAN.md` to mark 5c done with the explicit "templates
      + 360dialog deferred" note.

### 5c.6 — Templates + 360dialog (follow-up phase)

Deferred package:
- 360dialog provider (similar to Cloud, different URL/auth).
- Template sync from Graph API.
- Template parameter substitution.
- Attachments (needs media download + Phase 10 storage).
- Embedded signup.
- Reauthorization.
- Phone normalization (AR/BR helpers).

---

## Commit style

`phase5c: <area>: <short summary>` — one commit per milestone.
