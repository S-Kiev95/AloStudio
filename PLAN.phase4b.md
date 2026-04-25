# Phase 4b — Conversations/Messages: realtime + dispatch fan-out

**Why split from 4a:** 4a shipped the persistence + HTTP surface. 4b
wires the *reactive* side — Redis pub/sub, WebSocket broadcasts,
activity-message fan-out, and the filter DSL that powers conversation
index/search.

**Reference anchors (verbatim paths under `reference/chatwoot/`):**

* `app/dispatchers/{dispatcher,sync_dispatcher,async_dispatcher}.rb`
* `app/listeners/action_cable_listener.rb`
* `app/channels/room_channel.rb`
* `app/channels/application_cable/{channel,connection}.rb`
* `app/jobs/action_cable_broadcast_job.rb`
* `app/models/concerns/activity_message_handler.rb`
* `app/models/concerns/{assignee,priority,label,team}_activity_message_handler.rb`
* `app/services/{filter_service,conversations/filter_service}.rb`
* `app/finders/conversation_finder.rb`
* `app/controllers/api/v1/accounts/conversations_controller.rb` — the
  six endpoints not covered in 4a (filter/search/toggle_typing/
  attachments/transcript/messages#update).

---

## Milestones

Each milestone ships in its own commit. The tests suite stays green
after every commit.

### 4b.1 — Redis-backed EventDispatcher

Replace the no-op stub at `app/domains/conversations/events.py` with a
Redis publisher. Event names + payload shapes stay identical (the stub
already matches Chatwoot's `lib/events/types.rb`).

**Tasks:**
- [ ] `app/core/realtime.py` — thin wrapper around `redis.asyncio.Redis`
      with `publish(channel, payload)` + a module-level singleton that
      respects the `REDIS_URL` setting.
- [ ] `EventDispatcher.dispatch()` → delegates to a new
      `ActionCableListener` that translates each event name into the
      right channel list (`pubsub_token` + `account_<id>`) and publishes
      the `{event, data}` envelope Chatwoot uses.
- [ ] Unit tests with a stub Redis + integration test using `fakeredis`.

### 4b.2 — `/cable` WebSocket endpoint (ActionCable-compatible)

FastAPI WS endpoint that looks enough like Rails' ActionCable that
Chatwoot's frontend (and any client that follows the protocol) can
connect.

**Protocol subset we implement:**
- `welcome` — sent on connect.
- `confirm_subscription` — echo back the identifier the client sent.
- `ping` — every 30s so clients don't time out.
- Forwarding — when Redis publishes to a channel the client subscribed
  to, send `{identifier, message: {event, data}}`.

**Tasks:**
- [ ] `app/core/realtime/cable.py` — WS handler + Redis subscriber pump.
- [ ] Auth: `pubsub_token` from query string → look up `User` or
      `ContactInbox`, reject on miss.
- [ ] Mount at `/cable` (Chatwoot-compatible path).
- [ ] Integration test: two clients subscribed to the same channel both
      receive an event fired from a third HTTP call.

### 4b.3 — ActivityMessageHandler

Insert `message_type=activity` rows on state changes + fire
`MESSAGE_CREATED`.

**Covered transitions (Phase 4b):**
- Status change (`resolved`/`open`/`pending`/`snoozed`).
- Priority change.
- Assignee change.
- Team change.
- Label list change (requires the `Label` + `Tagging` models — land in
  this milestone).
- Mute/unmute (reuse the existing `mute_conversation` router endpoints).

**Deferred to later phases:**
- SLA policy change → Phase 9 (SLA model not in scope yet).
- AutomationRule branches (`automation_status_change_activity_content`)
  → Phase 6.

**Tasks:**
- [ ] `Label` + `Tagging` models + migration (acts-as-taggable-on subset
      — one tag-table, one tagging-join, no nested tag contexts).
- [ ] `app/domains/conversations/activity.py` — content templates
      matching `config/locales/en.yml` `conversations.activity.*`.
- [ ] Hook into `toggle_status` / `toggle_priority` /
      `update_custom_attributes` / mute+unmute / new label write paths.
- [ ] Activity row fires `MESSAGE_CREATED` so the realtime layer
      broadcasts it.

### 4b.4 — FilterService + ConversationFinder subset

Port enough of the two services to cover the real-world conversation
index/search queries. Full custom-attribute filter arrays land when
we port Campaign + Report filters in later phases.

**Operators (4b subset):**
- `equal_to`, `not_equal_to`
- `contains`, `does_not_contain`
- `is_present`, `is_not_present`

**Standard attributes:** `status`, `priority`, `assignee_id`,
`team_id`, `inbox_id`, `labels`, `created_at`, `last_activity_at`.

**Tasks:**
- [ ] `app/domains/conversations/finder.py` — `conversation_finder()`
      function taking the ConversationFinder params and returning the
      same shape our index already produces.
- [ ] `app/domains/conversations/filter.py` — `conversation_filter()`
      for the custom-attribute-payload DSL.
- [ ] New endpoint: `POST /conversations/filter` (body is the filter
      array; response mirrors `/conversations`).
- [ ] `GET /conversations/search` — query-string `q` (free text).
- [ ] Pagination helper shared with 4a.

### 4b.5 — Leftover 4a-adjacent endpoints

- [ ] `POST /conversations/:id/toggle_typing_status` — just a broadcast.
- [ ] `GET /conversations/:id/attachments` — paginated attachments
      list (reuses the attachment presenter from 4a).
- [ ] `PATCH /conversations/:conv_id/messages/:id` — API-inbox only
      (permitted_params = `target_language`, `status`, `external_error`).
      `target_language` triggers translation — see deferred list below.

### 4b.6 — Tests + PLAN updates

- [ ] Integration tests for every endpoint above.
- [ ] Parity tests (stateless gate pattern from 4a).
- [ ] Update `PLAN.md` phase table + mark 4b done.

---

## Deferred to later phases (logged here, not implemented in 4b)

- `ConversationReplyMailer` + `SendReplyJob` — needs SMTP (Phase 5b).
- `/conversations/:id/transcript` — same (Phase 5b).
- `messages#retry` — needs the job queue + real channel outbound
  (Phase 5b).
- `messages#translate` — needs Google Translate integration (Phase 5b).
- `OnlineStatusTracker` (presence heartbeat on `RoomChannel`) — needs
  the Redis TTL heartbeat pattern (Phase 4b.7 stretch, or 4c).
- `ConversationParticipants` + `CONVERSATION_MENTIONED` — needs the
  `Mention` model. Touches 4b and 9 (mentions power notifications).
- `AutomationRule` branches of `ActivityMessageHandler` — Phase 6.
- `SlaActivityMessageHandler` — Phase 9.
- `PermissionFilterService` — Phase 4c (role-based view scoping lives
  alongside AutoAssignment).

---

## Commit style

`phase4b: <area>: <short summary>` — one commit per milestone, each
self-contained and green against `pytest`. Each commit message links
the Ruby file(s) ported + the parity/integration tests that prove it.
