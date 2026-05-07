# Phase 5f — Channel: SMS (Twilio + Bandwidth)

**Why this phase:** SMS rounds out the channel surface for the
critical channels. Twilio's also where WhatsApp-via-Twilio lives
(``Channel::TwilioSms`` with ``medium=whatsapp``) — porting Twilio
SMS first puts the foundation in place; the WhatsApp medium ships
as a 5f.6 follow-up.

**Reference anchors (verbatim paths under `reference/chatwoot/`):**

* `app/models/channel/twilio_sms.rb`
* `app/models/channel/sms.rb` (Bandwidth provider)
* `app/services/twilio/incoming_message_service.rb`
* `app/services/twilio/send_on_twilio_service.rb`
* `app/services/sms/incoming_message_service.rb`
* `app/services/sms/send_on_sms_service.rb`
* `app/controllers/twilio/callback_controller.rb`
* `app/controllers/webhooks/sms_controller.rb`
* `app/jobs/webhooks/twilio_events_job.rb`
* `app/jobs/webhooks/sms_events_job.rb`

---

## Two-channel scope

Chatwoot ships two SMS-capable channel models:

1. **`Channel::TwilioSms`** — Twilio's SMS API. Form-encoded webhook
   at ``POST /twilio/callback``. REST send via
   ``api.twilio.com/2010-04-01/Accounts/<sid>/Messages.json`` with
   HTTP Basic auth (account_sid:auth_token). Also covers Twilio's
   WhatsApp via ``medium=whatsapp`` (deferred to 5f.6).

2. **`Channel::Sms`** — Bandwidth (default provider). JSON webhook
   at ``POST /webhooks/sms/<phone_number>``. REST send via
   ``messaging.bandwidth.com/api/v2/users/<account_id>/messages``
   with HTTP Basic auth (provider_config['api_token']:
   provider_config['api_secret']).

Different wire shapes, different schemas, different routing —
ports as separate sub-milestones to keep diffs reviewable.

## Test strategy: respx (same as 5c-5e)

Both providers use plain HTTP without exotic auth (Twilio's signed-
URL validation is server-to-server only, not on inbound — we don't
need to verify Twilio's request signatures for parity). Outbound
mocks via respx; inbound payloads are crafted as fixtures.

---

## Milestones

### 5f.1 — Both channel models + migrations + InboxBuilder branches

**Tasks:**
- [ ] `TwilioSms` SQLModel with the (account_sid, phone_number) unique
      pair + the standalone unique indexes on phone_number and
      messaging_service_sid.
- [ ] `SmsChannel` SQLModel for Bandwidth — phone_number unique +
      provider_config JSONB.
- [ ] Two Alembic migrations (one per channel — keeps the diff
      bisectable).
- [ ] Add `CHANNEL_TYPE_TWILIO_SMS` + `CHANNEL_TYPE_SMS` constants.
- [ ] InboxBuilder ``twilio_sms`` branch validating account_sid +
      auth_token + (phone_number OR messaging_service_sid).
- [ ] InboxBuilder ``sms`` branch validating phone_number +
      provider_config['api_token'] + ['api_secret'] + ['account_id']
      (bandwidth fields).
- [ ] Tests: builder happy paths + uniqueness constraints.

### 5f.2 — Twilio webhook receiver + inbound processor

Twilio's webhook is form-encoded. We accept both
``application/x-www-form-urlencoded`` and ``multipart/form-data``
since Twilio uses one or the other depending on whether MMS media
is attached.

**Tasks:**
- [ ] `app/domains/twilio/router.py` —
        - `POST /twilio/callback` — receives the form payload.
- [ ] `app/domains/twilio/incoming.py` —
        ``process_twilio_webhook(session, params)``. Resolves the
        channel by ``MessagingServiceSid`` first, fallback to
        ``(AccountSid, To)`` lookup. Looks up / creates Contact +
        ContactInbox keyed by ``From`` (the phone number with
        ``+`` prefix). Stamps Twilio's ``SmsSid`` on
        ``messages.source_id``.
- [ ] Idempotent on SmsSid.
- [ ] Tests: form-encoded payload with both SMS-only and MMS
        variants (the latter has ``MediaUrl0`` + ``MediaContentType0``
        keys we accept but don't process — Phase 10 storage).

### 5f.3 — Twilio outbound

Twilio's REST API uses HTTP Basic auth. We POST to
``api.twilio.com/2010-04-01/Accounts/<sid>/Messages.json`` with
form-encoded body.

**Tasks:**
- [ ] `app/domains/twilio/sender.py` —
        ``send_sms_twilio(session, channel, message, to_phone)``.
        Body: ``{To, Body, From OR MessagingServiceSid, StatusCallback}``.
        Returns Twilio's ``sid`` stamped onto ``source_id``.
- [ ] Hook into ``_apply_message_post_create`` for outgoing
        Channel::TwilioSms messages.
- [ ] Tests: respx mocks Twilio's REST endpoint; assert URL +
        Basic auth header + form body shape.

### 5f.4 — Bandwidth webhook + ingest + outbound (one milestone)

Bandwidth is much smaller than Twilio so we ship it as one
milestone. Webhook payload is JSON; outbound POSTs to Bandwidth's
messaging API with HTTP Basic auth using ``provider_config``.

**Tasks:**
- [ ] `app/domains/sms_bandwidth/router.py` —
        `POST /webhooks/sms/{phone_number}` accepts the JSON
        payload (Bandwidth sends an array — one webhook per delivery
        callback or inbound message).
- [ ] `incoming.py` — ``process_bandwidth_webhook(session, payload,
        phone_number)``. Resolves channel by phone_number, walks
        the ``message`` array, creates rows per inbound. Idempotent
        on Bandwidth's ``id``.
- [ ] `sender.py` — ``send_sms_bandwidth(session, channel, message,
        to_phone)``. POSTs ``{to, from, text, applicationId}`` to
        ``messaging.bandwidth.com/api/v2/users/<account_id>/messages``
        with Basic auth (provider_config token+secret).
- [ ] Tests against respx-mocked Bandwidth.

### 5f.5 — Parity tests + close 5f

- [ ] Cross-backend parity for Twilio + SMS endpoints.
- [ ] Update `PLAN.md` to mark 5f done.

### 5f.6 — Twilio WhatsApp medium (follow-up)

Channel::TwilioSms with ``medium=whatsapp`` — same auth/transport,
different message shape (Twilio prepends ``whatsapp:`` to the
``To`` field). Skipped in this phase to keep diffs focused.

---

## Deferred

* **MMS media downloads** — Twilio sends ``MediaUrl0..N`` URLs.
  Storage lands with Phase 10.
* **Twilio request signature validation** (``X-Twilio-Signature``
  header) — production hardening, Phase 9.
* **Delivery status callbacks** — Twilio ``DeliveredStatus`` /
  ``MessageStatus`` updates, Bandwidth ``message-delivered`` event.
  We accept the incoming webhook but don't update message status
  in 5f; ports later in 5f hardening.
* **Templates** (``Twilio::CsatTemplateService``, content_templates
  JSONB sync) — Phase 9.
* **Bandwidth inbound_messages_callback** delivery-status webhooks.
* **Twilio WhatsApp** (medium=whatsapp) — sub-phase 5f.6.

---

## Commit style

`phase5f: <area>: <short summary>` — one commit per milestone.
