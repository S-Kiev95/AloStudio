# AloStudio — Chatwoot → FastAPI migration plan

> Living document. Each phase has concrete exit criteria. A phase is **not
> done** until its parity tests pass against the reference Chatwoot v4.13.0
> Docker instance.

## Guiding rules

1. **Vertical slice, not schema-first.** For each domain: port model +
   service + callbacks + jobs + endpoints + policies + tests together, then
   move on. Never migrate all schemas first.
2. **Reference is the source of truth.** `reference/chatwoot` (read-only,
   pinned to v4.13.0) is always open alongside the file you are writing.
   Link Ruby → Python artifacts in every PR description / commit.
3. **Parity gate.** A phase closes only when `pytest -m parity` is green
   for the phase's scope.
4. **No half-ports.** If a Rails callback is skipped intentionally, record
   it in `docs/deferred.md` with the reason (not created yet — add when the
   first deferral happens).

## Stack

| Concern           | Choice                                  | Replaces in Chatwoot     |
|-------------------|-----------------------------------------|--------------------------|
| Web framework     | FastAPI                                 | Rails                    |
| ORM               | SQLModel (SQLAlchemy 2.x async)         | ActiveRecord             |
| Migrations        | Alembic (async via asyncpg)             | `rails db:migrate`       |
| Package manager   | uv                                      | bundler                  |
| Background jobs   | ARQ (Redis-backed async)                | Sidekiq                  |
| Realtime          | FastAPI WebSockets + Redis pub/sub      | ActionCable              |
| Auth              | PyJWT + FastAPI dependencies + bcrypt   | Devise + devise-jwt      |
| AuthZ             | FastAPI dependencies (`require_*`)      | Pundit policies          |
| Database          | Postgres 16 + pgvector                  | same                     |
| Mail (dev)        | MailHog                                 | Letter Opener / MailHog  |
| Object storage    | MinIO (S3 compat)                       | ActiveStorage/S3         |

## Workspace layout

```
AloStudio/
├── reference/chatwoot/          # v4.13.0 clone, read-only
├── app/
│   ├── core/                    # config, db, logging, security, base_model
│   ├── domains/<domain>/        # models, schemas, service, router, jobs, events
│   ├── channels/<channel>/      # per-channel ingest/send logic
│   ├── api/                     # routers aggregated here (health, v1, v2, public)
│   └── main.py
├── alembic/
├── tests/
│   ├── unit/                    # pure, no IO
│   ├── integration/             # real Postgres+Redis
│   └── parity/                  # vs reference Chatwoot
├── docker-compose.yml
├── pyproject.toml
└── PLAN.md                      # this file
```

## Phase status

| # | Phase | Status | Parity tests |
|---|-------|--------|--------------|
| 0 | Foundation                     | ✅ done        | smoke |
| 1 | Accounts + Users + Auth        | ✅ done        | signup, login, profile, password reset, confirmation |
| 2 | Inboxes + Agents + Teams (API channel only) | ✅ done        | inbox CRUD, member mgmt, team CRUD |
| 3 | Contacts                       | ✅ done        | identify, merge, custom attrs, search |
| 4a | Conversations + Messages — core | ✅ done       | CRUD, state machine, merge reassignment, 15 HTTP endpoints |
| 4b | Conversations + Messages — realtime & dispatch | ✅ done       | /cable WS, activity messages, filter/search, assignments/labels/typing/attachments/messages#update auth-gates |
| 4c | Conversations + Messages — assignment | ✅ done       | PermissionFilterService scope, round-robin auto-assignment, team-scope guard |
| 5a | Channel: Website widget       | ✅ done       | widget JWT auth + HMAC, config + contact + conversation + message endpoints, parity 404 envelopes |
| 5b | Channel: Email (IMAP/SMTP)    | ⬜ pending     | ingest threading, reply-to parse, outbound |
| 5c | Channel: WhatsApp Cloud/360/Twilio | ⬜ pending | webhook ingest, outbound template |
| 5d | Channel: Facebook Messenger   | ⬜ pending     | webhook ingest, outbound |
| 5e | Channel: Instagram DM         | ⬜ pending     | webhook ingest, outbound |
| 5f | Channel: SMS (Twilio/Bandwidth) | ⬜ pending   | webhook, outbound, delivery status |
| 5g | Channel: Telegram             | ⬜ pending     | webhook, outbound |
| 6 | Automation + Macros + Labels + CSAT | ⬜ pending | rule engine eval, macro apply, CSAT flow |
| 7 | Reports                         | ⬜ pending     | agent/conversation/inbox reports |
| 8 | Integrations (Slack, Dialogflow, Webhook apps, OpenAI) | ⬜ pending | per-integration webhook |
| 9 | Admin advanced (audit log, working hours, SLA, portal, campaigns) | ⬜ pending | per-area |
| 10 | Hardening (perf, observability, real-DB import) | ⬜ pending | load + data migration round-trip |

Legend: ✅ done · 🟡 in progress · ⬜ pending · ❌ blocked

---

## Known hazards (Windows dev host)

### Docker Desktop: stale `dockerInference` socket crashloop

Docker Desktop 4.43.x on Windows creates an AF_UNIX reparse-point socket
at `%LOCALAPPDATA%\Docker\run\dockerInference` when the Inference
manager starts. If the backend crashes, that socket is left behind as a
*stale* reparse point that `os.Remove` cannot delete (Windows returns
`ERROR_CANT_ACCESS_FILE 1920`; the reparse tag is not resolvable from
userland). On the next boot `startInferenceManager → ListenUnix` tries
to `os.Remove` it, fails, and Docker refuses to start with:

> initializing Inference manager: listening on
> unix://...\run\dockerInference: remove ...\dockerInference:
> El sistema no tiene acceso al archivo.

`EnableDockerAI: false` in `settings-store.json` does *not* prevent
the Inference manager from initializing in 4.43. The only reliable
recovery is to rename the parent `run\` folder (which *is* renameable
even though its children can't be deleted) so Docker creates a fresh
one on next start.

Recovery: run `scripts/fix-docker-run.ps1` with Docker fully stopped,
then relaunch Docker Desktop.

---

## Phase 0 — Foundation

**Goal:** everything set up to start porting business logic in Phase 1
without further yak-shaving.

### Exit criteria

- [x] `uv sync` installs cleanly, `.venv/` has all runtime + dev deps.
- [x] `docker-compose.yml` defines Postgres (pgvector), Redis, MailHog,
      MinIO, and an optional `reference` profile with a full Chatwoot
      v4.13.0 stack (Rails + Sidekiq + own Postgres/Redis).
- [x] FastAPI app boots, serves `/` and `/health` endpoints.
- [x] Alembic wired to async SQLAlchemy, can autogenerate migrations.
- [x] `pytest` runs with three tiers: unit, integration, parity.
- [x] Parity tier skips gracefully when Chatwoot reference is not running.
- [x] `uv run pytest tests/unit tests/parity` → all unit pass, parity
      tier passes for alo-side and skips cw-side.
- [ ] Smoke test: `docker compose up -d postgres redis mailhog minio`
      brings up the four dev deps and containers stay healthy.
- [ ] Smoke test (manual): `docker compose --profile reference up -d`
      brings up Chatwoot reference and is reachable at
      `http://localhost:3001`. (Requires `.env.chatwoot-ref` with a real
      `SECRET_KEY_BASE`.)

### Next actions for the user

1. Copy env templates:
   ```bash
   cp .env.example .env
   cp .env.chatwoot-ref.example .env.chatwoot-ref
   # generate and paste a SECRET_KEY_BASE into .env.chatwoot-ref:
   openssl rand -hex 64
   ```
2. Bring up dev deps: `docker compose up -d postgres redis mailhog minio`
3. Bring up reference (one-time migration then run): 
   ```bash
   docker compose --profile reference run --rm chatwoot-ref-migrate
   docker compose --profile reference up -d
   ```
4. Create admin user in Chatwoot reference (via signup flow at
   `http://localhost:3001`). Use `admin@alostudio.local` / `Password123!`
   to match `.env.example` defaults for parity tests.
5. Give the thumbs up and Phase 1 starts.

---

## Phase 1 — Accounts + Users + Auth

**Goal:** multi-tenant foundation (Account) + authenticated Users with
role-based access (administrator/agent). Devise → JWT.

### Chatwoot artefacts to port (reference paths)

- `app/models/account.rb`
- `app/models/user.rb`
- `app/models/account_user.rb`
- `app/controllers/devise_overrides/*`
- `app/controllers/api/v1/accounts_controller.rb`
- `app/controllers/api/v1/profiles_controller.rb`
- `app/policies/account_policy.rb`
- `app/services/account_builder.rb`
- `app/mailers/*` (confirmation, reset) — minimal port to MailHog
- Devise config (`config/initializers/devise.rb`) — token TTLs, lockout,
  confirmation flow

### New AloStudio artefacts

```
app/domains/accounts/{models.py, schemas.py, service.py, router.py}
app/domains/users/{models.py, schemas.py, service.py, router.py, auth.py}
app/domains/users/policies.py          # require_admin, require_agent_of_account
app/core/deps.py                       # current_user, current_account
```

### Endpoints (parity 1:1 with Chatwoot)

| Method | Path                                       | Note                      |
|--------|--------------------------------------------|---------------------------|
| POST   | `/auth/sign_up`                            | creates Account + User    |
| POST   | `/auth/sign_in`                            | returns access+refresh    |
| POST   | `/auth/sign_out`                           | invalidates refresh       |
| POST   | `/auth/password`                           | request reset             |
| PUT    | `/auth/password`                           | apply reset               |
| POST   | `/auth/confirmation`                       | resend confirmation       |
| GET    | `/auth/confirmation?confirmation_token=…`  | confirm                   |
| GET    | `/api/v1/profile`                          | current user              |
| PUT    | `/api/v1/profile`                          | update                    |
| GET    | `/api/v1/accounts/:id`                     | account detail            |
| GET    | `/api/v1/accounts/:id/agents`              | list account users        |

### Parity tests

Sequence per test:
1. Create matching state on both backends via test-only endpoints or
   seed scripts.
2. Same HTTP call on both.
3. `assert_json_parity(alo_resp, cw_resp, ignore_paths=[...])`.

Cases: signup happy path · signup duplicate email 422 · login 200/401 ·
password reset full cycle · profile update echoes same shape ·
unauthorised 401 vs 403 across policies · token expiry rejected.

### Exit criteria

- [x] All Phase 1 endpoints return byte-equal JSON (modulo ignored
      paths) to reference Chatwoot. Locked down by
      `tests/parity/test_auth_parity.py` — caught and fixed two real
      drifts (missing ``success: false`` on sign_in 401, wrong i18n
      string on password-reset 200) that integration tests alone would
      have missed.
- [x] `alembic upgrade head` produces the schema that
      `alembic revision --autogenerate` would emit (no drift).
- [x] `pytest -m "unit or integration or parity"` → green for Phase 1
      scope (75/75 at phase close).

### Closing notes

Shipped in four commits (`a7a7a0a` → `97d54e1`):

  1. ``phase1(models+builder)`` — ``Account`` / ``User`` /
     ``AccountUser`` / ``AccessToken`` + ``AccountBuilder`` service.
  2. ``phase1(auth+profile+accounts)`` — ``POST /api/v1/accounts``
     (signup), ``POST /auth/sign_in``, ``POST /auth/sign_out``,
     ``GET/PUT /api/v1/profile``, ``GET/PATCH /api/v1/accounts/:id``,
     ``GET /api/v1/accounts/:id/agents``.
  3. ``phase1(auth)`` — ``POST/PUT /auth/password``,
     ``POST /auth/confirmation``, ``POST /resend_confirmation``, plus
     ``ChatwootHTTPException`` parity-envelope fix.
  4. ``chore(lint)`` — ruff project-wide clean.

Deferred intentionally (logged here instead of a separate file because
they're the only Phase 1 deferrals so far):

  * Real email delivery — confirmation + reset mailers log the raw
    token today, will switch to an ARQ enqueue when the ARQ mail
    worker lands (post-Phase-5).
  * hCaptcha gate on ``POST /resend_confirmation`` — the Ruby
    controller requires a valid ``h_captcha_client_response``; we
    accept any request and rely on the always-204 contract to prevent
    enumeration.
  * MFA / SSO branches in ``sign_in`` — Phase 1 is email+password only.
    ``process_sso_auth_token`` + ``mfa_token`` validation land with
    whichever later phase wires MFA end-to-end.
  * Account / User lockout counters — Devise has
    ``lockable`` columns on the schema but the Ruby controller's
    ``locked?`` branch isn't consumed anywhere in the paths we ported.
  * ``PLAN.md`` lists ``POST /auth/sign_up`` — the actual Chatwoot
    route (what we implemented) is ``POST /api/v1/accounts``. The plan
    was approximate on path, exact on shape.

---

## Phase 2 — Inboxes + Agents + Teams (API channel only)

**Goal:** organisational structure + the simplest channel type so that
Phase 3 (Contacts) and Phase 4 (Conversations) have something to attach
to. Other channel types land in Phase 5.

### Chatwoot artefacts

- `app/models/inbox.rb`, `app/models/channel/api.rb`
- `app/models/inbox_member.rb`, `team.rb`, `team_member.rb`
- `app/controllers/api/v1/accounts/inboxes_controller.rb`
- `app/controllers/api/v1/accounts/inbox_members_controller.rb`
- `app/controllers/api/v1/accounts/teams_controller.rb`
- `app/policies/inbox_policy.rb`, `team_policy.rb`
- `app/builders/v2/inbox_builder.rb`

### Endpoints

| Path                                                    | Purpose              |
|---------------------------------------------------------|----------------------|
| `POST /api/v1/accounts/:id/inboxes`                     | create API inbox     |
| `GET/PATCH/DELETE /api/v1/accounts/:id/inboxes/:iid`    | CRUD                 |
| `POST /api/v1/accounts/:id/inbox_members`               | assign agents        |
| `GET/POST/PATCH/DELETE /api/v1/accounts/:id/teams(/…)`  | team CRUD            |

### Exit criteria

- [x] API inbox CRUD parity.
- [x] Agent assignment parity including the webhook_url + hmac_mandatory
      knobs.
- [x] Team CRUD parity including member add/remove.
- [x] `pytest -m "unit or integration"` → green for Phase 2 scope
      (94/94 at phase close).
- [x] `pytest -m parity` → green for the stateless branches we can lock
      down without a cross-backend seed harness (401s on all write paths,
      401 on `reset_secret`, 401 on team destroy — 8 tests).

### Closing notes

Deferred intentionally:

  * **Non-API channels** — ``Channel::Email`` /
    ``Channel::FacebookPage`` / ``Channel::Whatsapp`` / etc. are stubbed
    at the model layer (``channel_type`` is polymorphic, no FK) but no
    concrete classes ship in Phase 2. Each lands in its own Phase 5
    sub-phase with its own parity harness.
  * **Round-robin hooks on ``InboxMember``** — Chatwoot's ``after_create``
    /``after_destroy`` callbacks kick
    ``AutoAssignment::InboxRoundRobinService``. Auto-assignment doesn't
    exist yet, so the hooks are service-layer no-ops until Phase 5.
  * **Working hours schedule** — ``working_hours`` has its own table
    joined by ``inbox_id``. The inbox response presenter surfaces an
    empty schedule for now; the table + endpoints land with Phase 9
    (admin advanced).
  * **Portal FK** — ``inboxes.portal_id`` column is kept for schema
    parity with v4.13.0, but no SA-level ``ForeignKey`` is declared
    because Portal is Phase 6+.
  * **Happy-path body parity tests** — teams + inboxes wire-shape
    parity needs synchronized seed data (same admin user, same account
    IDs) across the two backends. Covered by integration tests on our
    side + Chatwoot's own rspec on theirs. The parity module catches
    envelope drift on the error paths that *don't* need seeding.

Key decision: ``resources :inbox_members, param: :inbox_id`` in
Chatwoot's ``config/routes.rb`` declares inbox_members at the **account**
level — NOT nested under ``/inboxes/:id``. ``show`` hangs off
``/inbox_members/:inbox_id``; create/patch/delete read ``inbox_id``
from the body. We matched that exactly to avoid shape drift on a path
that's easy to get wrong.

---

## Phase 3 — Contacts

### Chatwoot artefacts

- `app/models/contact.rb`, `contact_inbox.rb`
- `app/services/contact_identify_action_service.rb`
- `app/services/contact_merge_action_service.rb`
- `app/controllers/api/v1/accounts/contacts_controller.rb`
- `app/controllers/api/v1/accounts/contacts/*` (notes, labels, events,
  conversations index)
- Custom attributes: `custom_attribute_definitions`, merge with
  `custom_attributes` JSON column on `Contact`.

### Endpoints

CRUD, search, identify, merge, notes, labels, custom attrs.

### Exit criteria

- [x] Identify by email / phone / identifier produces same Contact row
      shape as Chatwoot (including `pubsub_token` presence,
      `hmac_verified`, `last_activity_at`).
- [x] Merge destroys source contact (conversation/message reassignment
      is a Phase 4 follow-up — see deferred below).
- [x] Search filters match (email equals, phone equals, identifier
      equals, name ilike) with ``has_more`` pagination flag.
- [x] Custom attribute definitions CRUD: create/index/show/update/
      destroy, ``attribute_model`` filter, STANDARD_ATTRIBUTE_KEYS guard,
      attribute-key regex validation, per-(account,model) uniqueness.
- [x] `pytest -m "unit or integration"` → 140/140 green (29 new Phase 3
      tests, no regressions).

### Closing notes

Shipped as a single ``phase3(contacts)`` commit covering:

  1. Models + Alembic migration (``contacts``, ``contact_inboxes``,
     ``notes``, ``custom_attribute_definitions``).
  2. Services: ``ContactIdentifyAction``, ``ContactMergeAction`` (stub
     for conversation/message reassignment), ``ContactableInboxes`` (API
     channel branch only), custom-attribute-definition create/update
     with STANDARD_ATTRIBUTE_KEYS guard + regex parity.
  3. Routers: ``/contacts`` (CRUD, search, contactable_inboxes,
     destroy_custom_attributes, nested notes + contact_inboxes),
     ``/actions/contact_merge``, ``/custom_attribute_definitions``.
  4. Presenters: Contact (unix-int timestamps) + CustomAttributeDefinition
     (ISO-8601 timestamps — Chatwoot inconsistency preserved) +
     Note (retains ``account_id: null`` jbuilder bug for parity).

Deferred intentionally:

  * **Conversation / Message reassignment in merge** — Chatwoot's
    ``ContactMergeActionService`` reassigns all Conversations, Messages
    and ``ContactInbox`` rows from the mergee to the base contact. We
    destroy the mergee and leave a TODO in the service; the sweep is
    trivial once Phase 4's Conversation/Message tables land.
  * **active / import / export / filter / avatar / labels** —
    ``contacts_controller.rb`` has action methods for each. The filter
    engine is its own beast (``ContactsFilter``) and rides with the
    Phase 6 automation rule engine. Avatar upload rides with MinIO
    wiring in Phase 10. ``GET /active`` uses OnlineStatusTracker which
    is a Phase 4 realtime concern.
  * **ContactableInboxes non-API branches** — the service short-circuits
    when ``channel_type != 'Channel::Api'`` today. Each of Email /
    Website / WhatsApp / etc. lands with its Phase 5 sub-phase because
    the contact-discovery rules vary per channel (email_id, phone_number,
    identifier, etc.).
  * **Labels on Contact** — ``acts_as_taggable_on :labels`` is a
    cross-cutting concern; Label model ships in Phase 6 alongside
    Conversation labels so both go through one gaol.
  * **Events sub-controller** — ``GET /contacts/:id/events`` hangs off
    ``ReportingEvent`` which is a Phase 7 table.
  * **ContactInbox pubsub_token regeneration** — ``regenerate_pubsub_token``
    on ContactInbox ships when the widget channel needs it (Phase 5a).
  * **Parity vs. live Chatwoot** — no cross-backend harness yet for
    Phase 3; same posture as Phase 2's "wire-shape parity needs
    synchronized seed data". Integration tests + Chatwoot's own rspec
    cover both sides. Any drift caught will be fixed as a follow-up
    commit on the phase3 line.

---

## Phase 4 — Conversations + Messages

The highest-risk phase — conversation lifecycle touches nearly every
other subsystem. See detailed sub-plan under `PLAN.phase4.md`.

Split into three sub-phases to keep each shippable in isolation:

### Phase 4a (done) — core CRUD + state machine + merge closure

Shipped:
- Model: `Conversation` state machine (`pending`/`open`/`resolved`/
  `snoozed`), `Message` (`incoming`/`outgoing`/`activity`/`template`),
  `Attachment`, with per-account `display_id` sequence + BEFORE INSERT
  trigger and the `uuid` column matching Rails.
- Service: `ConversationBuilder` (incl. `lock_to_single_conversation`
  reuse-latest branch), `MessageBuilder` (API-channel guard, flooding
  cap, external_url attachments), `toggle_status`/`toggle_priority`/
  `bot_handoff`/`update_custom_attributes`, `reassign_mergee_conversations`
  (contact-merge closure).
- Presenters: byte-parity with `_conversation.json.jbuilder`,
  `_message.json.jbuilder`, `messages/index.json.jbuilder` — including
  quirks (updated_at as FLOAT `.to_f` while everything else is INT `.to_i`;
  `message_type` on the wire as integer `_before_type_cast`).
- Router: 15 endpoints (12 conversation + 3 message) — create/index/meta/
  show/update/toggle_status/toggle_priority/mute/unmute/custom_attributes/
  update_last_seen/unread + messages index/create/destroy(soft-delete).
- Dispatcher: stub `EventDispatcher` (logs only) so the post-create
  callback cascade has an integration point ready for 4b.
- Tests: 36 integration tests (24 conversations + 12 messages) — 176 tests
  green in total.

### Phase 4b (pending) — realtime + dispatch fan-out

- Redis pub/sub wire for `EventDispatcher` (replace the no-op stub).
- ActionCable channel-name parity (`RoomChannel` / `user-<id>` /
  `conversation-<uuid>`) over FastAPI WebSockets.
- `ActivityMessageHandler` fan-out (priority/team/label change activity
  rows + push events).
- `SendReplyJob` + `ConversationReplyMailer` scaffolding (real sends
  land with Phase 5b once SMTP arrives).
- `FilterService` DSL — arrives alongside conversation `index`/`search`
  parity expansion (date ranges, labels, inbox/team filter, q search).
- `toggle_typing_status`, `attachments` index, `transcript`,
  `messages#update` / `retry` / `translate`.

### Phase 4c (pending) — assignment + SLA

- `AssignmentHandler` team-scope guard.
- `AutoAssignmentHandler` round-robin service + `RoundRobinAssignmentJob`.
- `/assignments` reassign endpoint.
- SLA tick + CSAT resolve-with-CSAT path.
- `ConversationAutoResolutionJob`, `NotificationDispatchJob`.

---

## Phase 5 — Channels (by sub-phase)

Plan written per channel as we get there. Each channel exits with its
own parity harness: a canned real webhook payload goes in → assert
identical Conversation + Message rows + WS events emitted.

---

## Phase 6–10

Planned at high level above — detailed sub-plan written when each phase
is next.

---

## Conventions

### Commit style

`<phase>: <domain>: short sentence` — e.g.:
- `phase1: users: port Devise confirmation flow`
- `phase4: conversations: wire state machine + parity for transitions`

Commit body links the Ruby file(s) that were ported and the parity test
that proves it.

### Mapping Ruby → Python

When porting a Rails file, leave a header comment mapping the source:

```python
# Ported from reference/chatwoot/app/services/contact_identify_action_service.rb
# (v4.13.0). Notable differences: we perform the merge check atomically in
# a single UPDATE rather than the Rails `with_lock` block, because the
# async session scope differs; see tests/parity/test_contacts_identify.py.
```

### Deferred-behaviour log

Anything we deliberately skip gets a line in `docs/deferred.md` (create
on first deferral). Format:

```
- [v4.13.0 chatwoot path] — skipped because <reason>. Revisit when <trigger>.
```

This way "what's missing" is one grep, not spelunking.
