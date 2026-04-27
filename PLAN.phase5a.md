# Phase 5a — Channel: Website widget

**Why this phase:** the website widget (`Channel::WebWidget`) is the
public-facing surface contacts use to chat with us. It's the simplest
non-API channel — no third-party webhook, no OAuth, no rate-limiter
acrobatics — so it makes a good first port before tackling the
phone/social channels in 5c-5g.

**Reference anchors (verbatim paths under `reference/chatwoot/`):**

* `app/models/channel/web_widget.rb`
* `app/services/widget/token_service.rb` (+ `BaseTokenService`)
* `app/controllers/api/v1/widget/base_controller.rb`
* `app/controllers/api/v1/widget/configs_controller.rb`
* `app/controllers/api/v1/widget/contacts_controller.rb`
* `app/controllers/api/v1/widget/conversations_controller.rb`
* `app/controllers/api/v1/widget/messages_controller.rb`
* `app/controllers/concerns/website_token_helper.rb`
* `app/helpers/widget_helper.rb` (`build_contact_inbox_with_token`)
* `app/builders/contact_inbox_with_contact_builder.rb`

---

## Milestones

### 5a.1 — WebWidget model + migration + InboxBuilder extension

Adds the `channel_web_widgets` table mirroring Chatwoot's schema and
extends :class:`InboxBuilder` to accept `channel_type='web_widget'`
with the editable params (website_url, widget_color, welcome_*,
hmac_mandatory, allowed_domains, pre_chat_form_options).

**Tasks:**
- [ ] `app/domains/channels/web_widget/models.py` — `WebWidget`
      SQLModel with `website_token` (auto-generated) + `hmac_token`
      + the FlagShihTzu feature flags as a single integer.
- [ ] Alembic migration creating `channel_web_widgets` with the unique
      indexes on `website_token` + `hmac_token`.
- [ ] Extend `app/domains/inboxes/service.py::InboxBuilder` to accept
      `web_widget` in `_allowed_channel_types`. Map the params dict
      to a fresh `WebWidget` row (including default
      `pre_chat_form_options` JSON).
- [ ] Token service in `app/core/widget_token.py` — JWT encode/decode
      of `{source_id, inbox_id}` with a 180-day expiry, signed with
      `settings.secret_key`.
- [ ] Unit tests for the token roundtrip + InboxBuilder happy path on
      a fresh WebWidget inbox.

### 5a.2 — Widget base auth + config + contact endpoints

Read-only / contact-management surface. The widget JS calls these
before opening a conversation.

**Endpoints:**
- `POST /api/v1/widget/config?website_token=<t>` — bootstraps a
  ContactInbox + auth token for an anonymous visitor. Returns the
  widget config + the auth token JWT.
- `GET  /api/v1/widget/contact?website_token=<t>` (X-Auth-Token) —
  returns the resolved contact.
- `PATCH /api/v1/widget/contact?website_token=<t>` — updates the
  contact (`identify` semantics).
- `POST /api/v1/widget/contact/set_user?website_token=<t>` — sets
  `identifier` + verifies HMAC if mandatory.

**Tasks:**
- [ ] `app/domains/channels/web_widget/router.py` — endpoint handlers.
- [ ] FastAPI dependency `widget_context` resolves
      `(@web_widget, @contact, @contact_inbox)` from `website_token`
      query string + `X-Auth-Token` header.
- [ ] Auto-create ContactInbox + token when token is missing /
      decodes to a `source_id` no longer in DB.
- [ ] HMAC validation helper for `set_user` — reject 401 with the
      same envelope Rails uses (`{"error": "HMAC failed: ..."}`).

### 5a.3 — Widget conversation + message endpoints

The chat surface. Lets the contact post incoming messages, list
existing messages, toggle status, and update last-seen.

**Endpoints:**
- `GET  /api/v1/widget/conversations` — most recent conversation.
- `POST /api/v1/widget/conversations` — create a conversation +
  inline first message (mirrors the Rails create action; runs
  `ContactIdentifyAction` first when contact data is supplied).
- `GET  /api/v1/widget/messages` — paginated message list.
- `POST /api/v1/widget/messages` — send incoming message; auto-creates
  the conversation if there isn't one yet.
- `PATCH /api/v1/widget/messages/:id` — submit form responses
  (input_email, input_select).
- `POST /api/v1/widget/conversations/update_last_seen` — set
  `contact_last_seen_at`.
- `POST /api/v1/widget/conversations/toggle_typing` — same dispatch
  semantics as agent typing.
- `POST /api/v1/widget/conversations/toggle_status` — only when
  `web_widget.end_conversation` flag is on; resolves the conversation.

**Tasks:**
- [ ] Reuse `MessageBuilder` from `app.domains.conversations.service`
      with `message_type=incoming` + `sender_type=Contact` /
      `sender_id=contact.id`.
- [ ] Wire widget router under `/api/v1/widget` and mount in
      `app/main.py`.
- [ ] Skip the agent-side parts (filter DSL, custom_attributes) —
      the widget never hits them.

### 5a.4 — Tests + parity + PLAN update

- [ ] Integration tests for the full happy path: widget config ->
      send message -> agent receives via realtime broadcast (already
      ported in 4b).
- [ ] Parity tests: 401 / 404 envelopes for the new endpoints
      cross-backend.
- [ ] Update `PLAN.md` to mark 5a done.

---

## Deferred

* `direct_uploads_controller` — needs MinIO/ActiveStorage parity
  (Phase 10).
* `events_controller` — analytics events; not on the critical path
  for chat.
* `inbox_members_controller` — agent list rendering; needs avatar
  + presence (later).
* `labels_controller` — already exposed in the agent surface; widget
  uses it read-only for pre-applied labels (`messages#create labels`
  param). The first-message create path covers that already.
* `campaigns_controller` — Phase 9 (campaigns).
* Continuity-via-email (transcript link) — Phase 5b (SMTP).
* `/widgets` (the embed JS host) — front-end only, served by the SDK
  build. Out of scope for the API port.
* `apply_labels` on widget message create — pulls from
  `account.labels.where(title:)`. Trivial to add when we wire the
  message route; we'll port it in 5a.3 if the test demands it.

---

## Commit style

`phase5a: <area>: <short summary>` — one commit per milestone.
