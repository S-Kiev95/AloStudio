# Phase 4 sub-plan — Conversations + Messages

> Companion to `PLAN.md`. Phase 4 in the root plan was a single line; the
> actual surface covers ~40 controllers, ~25 jobs, ~12 callbacks across
> two models, and the realtime replacement for ActionCable. Split into
> three sub-phases so each can close cleanly on its own parity harness.

## Reference anchors (read-only, `reference/chatwoot/` v4.13.0)

Core models:
  * `app/models/conversation.rb` (+ concerns: `AssignmentHandler`,
    `AutoAssignmentHandler`, `ActivityMessageHandler`,
    `ConversationMuteHelpers`, `Labelable`, `UrlHelper`, `SortHandler`,
    `PushDataHelper`)
  * `app/models/message.rb`
  * `app/models/attachment.rb`
  * `app/models/mention.rb`, `conversation_participant.rb`

Services / builders:
  * `app/builders/conversation_builder.rb`
  * `app/builders/messages/message_builder.rb`
  * `app/services/auto_assignment/*`
  * `app/services/conversations/*` (filter, typing, message_window, etc.)

Controllers + jbuilder:
  * `app/controllers/api/v1/accounts/conversations_controller.rb`
  * `app/controllers/api/v1/accounts/conversations/*` (messages,
    assignments, labels, participants, draft_messages, direct_uploads)
  * `app/views/api/v1/models/_conversation.json.jbuilder`
  * `app/views/api/v1/models/_message.json.jbuilder`

Realtime:
  * `app/channels/room_channel.rb`
  * `app/listeners/action_cable_listener.rb`

Jobs:
  * `app/jobs/conversations/*`, `app/jobs/send_reply_job.rb`,
    `app/jobs/conversations/user_mention_job.rb`

## Sub-phase layout

| # | Sub-phase | Scope | Parity tests |
|---|-----------|-------|--------------|
| 4a | **Core: models + CRUD + state machine** | SQLModels, Alembic, builders, toggle_status, toggle_priority, reopen-on-incoming, jbuilder-parity presenters, CRUD routers, message destroy/retry, contact-merge closure (Phase 3 deferral). Event dispatch is a **no-op hook**. | CRUD wire shape, state transitions, filter envelope |
| 4b | **Realtime: WS + dispatcher** | Replace ActionCable with FastAPI WebSocket + Redis pub/sub. Wire `ActionCableListener` equivalents. Payload parity with `push_event_data`. Typing status. `update_last_seen`. | Each event payload diffs byte-for-byte against a recorded ActionCable frame |
| 4c | **Auto-assignment: round-robin** | `AutoAssignment::AgentAssignmentService` + `InboxRoundRobinService` + `RateLimiter` using Redis. Assignment-change activity messages. Team-scope and rate-limit parity. | Seeded N agents, assign M conversations, assert distribution matches |

Sub-phases ship as separate commits on the `phase4:` line so we can
bisect if any drift sneaks in.

## Phase 4a — Core (this commit)

### Tables (new)

  * `conversations` — columns per ruby model + every timestamp. FKs to
    `accounts`, `inboxes`, `contacts`, `contact_inboxes`, `users`
    (assignee), `teams`. Nullable FK columns for `sla_policy_id`,
    `campaign_id`, `assignee_agent_bot_id` — we keep the columns for
    schema parity but **no SA-level ForeignKey** until their owning
    phases land (same pattern as `inboxes.portal_id` in Phase 2).
  * `messages` — columns per ruby model. Polymorphic `sender_type` +
    `sender_id` without a concrete FK (Rails' own approach).
  * `attachments` — columns per ruby model. `file_type` enum. External
    URL only — ActiveStorage blob table doesn't ship here (Phase 10
    concern). `external_url` is text; we'll populate it from MinIO
    uploads in a later phase.
  * `mentions` — pivot for `Conversation`↔`User` @-mention tracking.
  * `conversation_participants` — pivot for `Conversation`↔`User`.

`conversations.display_id` uses a per-account sequence. Chatwoot uses a
DB trigger (`increment_conversation_count`). Port the trigger in the
migration — it's tiny and the alternative (compute in Python) races
under concurrency.

### Services

  * `ConversationBuilder` — mirror the ruby builder: if
    `inbox.lock_to_single_conversation?`, return the latest open
    conversation; else create. Fire state machine callbacks via
    post-flush hook.
  * `MessageBuilder` — handle attachments list, email header extraction
    (to/cc/bcc lives in `content_attributes['email']`), template_params
    validation, `in_reply_to` lookup via `source_id`. Defer liquid
    template rendering to Phase 4b/5 (email channel).
  * `StateMachineService` — `toggle_status`, `toggle_priority`,
    `bot_handoff`, `reopen_on_incoming`. Each method emits a
    `ConversationEvent(name, payload)` to the dispatcher.
  * `EventDispatcher` — stub interface with a single `dispatch(event)`
    method. Phase 4a ships an in-memory no-op implementation that logs.
    Phase 4b swaps in the Redis pub/sub backend.

### Presenters

Conversation wire shape (matches `_conversation.json.jbuilder`):

```
{
  additional_attributes, can_reply, channel (derived), contact_inbox,
  id (display_id!), inbox_id, messages (array, last 20), labels,
  meta {sender, assignee, team, hmac_verified, channel},
  status, custom_attributes, snoozed_until, unread_count,
  first_reply_created_at, priority, waiting_since, agent_last_seen_at,
  contact_last_seen_at, timestamp (last_activity_at as unix),
  created_at (unix), updated_at (unix), last_non_activity_message
}
```

Unix-int timestamps — parity with Contact presenter.

Message wire shape: `id, content, account_id, inbox_id, conversation_id
(display_id!), message_type, content_type, status, content_attributes,
created_at (unix), private, source_id, sender (push_event_data),
attachments (push_event_data[]), echo_id`.

### Routers

Under `/api/v1/accounts/{account_id}/`:

| Method | Path | Action |
|--------|------|--------|
| GET    | `conversations` | index, filters via querystring |
| POST   | `conversations` | create |
| GET    | `conversations/meta` | count by status |
| GET    | `conversations/search` | full-text (SQL ILIKE, no Elasticsearch) |
| POST   | `conversations/filter` | advanced filter DSL (deferred subset) |
| GET    | `conversations/:id` | show (by display_id) |
| POST   | `conversations/:id/toggle_status` | state machine |
| POST   | `conversations/:id/toggle_priority` | priority |
| POST   | `conversations/:id/mute` / `unmute` | mute contact |
| POST   | `conversations/:id/custom_attributes` | patch custom attrs |
| POST   | `conversations/:id/update_last_seen` | agent seen tick |
| GET    | `conversations/:id/attachments` | paginated attachment list |
| GET    | `conversations/:id/messages` | index |
| POST   | `conversations/:id/messages` | create (via MessageBuilder) |
| PATCH  | `conversations/:id/messages/:mid` | status update (API inbox) |
| DELETE | `conversations/:id/messages/:mid` | soft-delete |

Deferred to 4b: `toggle_typing_status`, `transcript`, `retry`.
Deferred to 4c: `assignments` nested endpoint.

### Phase 3 deferral closure

`ContactMergeAction` currently destroys the mergee but leaves
conversations/messages orphaned. Once Conversation and Message exist,
sweep in a single SQL `UPDATE`:

```sql
UPDATE conversations SET contact_id = :base WHERE contact_id = :mergee;
UPDATE messages SET sender_id = :base WHERE sender_type = 'Contact' AND sender_id = :mergee;
UPDATE contact_inboxes SET contact_id = :base WHERE contact_id = :mergee;
```

Plus the `conversations.contact_inbox_id` rewrite where needed.

### Exit criteria for 4a

- [ ] CRUD parity (index, show, create, toggle_status, toggle_priority,
      mute/unmute, custom_attributes).
- [ ] Message CRUD parity (index, create, destroy soft, status update).
- [ ] Reopen-on-incoming transition covered by a test (snoozed → open,
      resolved → open, pending bot-handoff stays pending).
- [ ] `waiting_since` ↔ `first_reply_created_at` dance correct under
      incoming→outgoing→resolve cycle.
- [ ] Contact merge sweeps conversations + messages (Phase 3 deferral
      closed).
- [ ] `pytest -m "unit or integration"` → green.

### Intentionally deferred from 4a

  * **Realtime dispatcher (ActionCable replacement)** → 4b.
  * **AutoAssignment round-robin** → 4c (the `AutoAssignmentHandler`
    hook calls a stub that logs and returns).
  * **Activity message generation** (assignee/team/priority/label/SLA
    changes spawn an `activity` message) → 4b, once the dispatcher is
    real. 4a emits activity messages synchronously for just the state
    transitions that have user-visible wire consequences (resolved /
    reopened), and stubs the rest.
  * **Message templates / hook execution** (greeting, CSAT, email
    collect, out-of-office) → 4b-lite or Phase 5.
  * **SLA / CSAT / Campaigns / Automation rules / Reporting events** →
    own phases (5/6/7). Columns exist, FKs are nullable, no SA
    ForeignKey declared.
  * **Email parsing (IMAP/MIME/quoted reply)** → Phase 5b (email
    channel).
  * **Attachment file upload pipeline** — attachments can be created
    with `external_url`, but the MinIO upload endpoint + ActiveStorage
    equivalent land in Phase 10.
  * **ConversationsFilter DSL** — Chatwoot's filter engine is shared
    with automation rules. 4a ships the minimum viable subset
    (status, assignee, inbox, team, labels). Full DSL rides with the
    rule engine in Phase 6.
  * **Nested controllers beyond messages** — assignments, labels,
    participants, draft_messages, direct_uploads. Each gets its own
    small commit on the phase4 line as needed.
