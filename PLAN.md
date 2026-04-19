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
| 2 | Inboxes + Agents + Teams (API channel only) | ⬜ pending | inbox CRUD, member mgmt, team CRUD |
| 3 | Contacts                       | ⬜ pending     | identify, merge, custom attrs, search |
| 4 | Conversations + Messages       | ⬜ pending     | state machine, assignment, WS events, notes |
| 5a | Channel: Website widget       | ⬜ pending     | widget auth, create conv from widget |
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

- API inbox CRUD parity.
- Agent assignment parity including the webhook_url + hmac_mandatory
  knobs.
- Team CRUD parity including member add/remove.

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

- Identify by email / phone / identifier produces same Contact row
  shape as Chatwoot (including `pubsub_token` presence, `hmac_verified`,
  `last_activity_at`).
- Merge destroys source contact, reassigns conversations & messages.
- Search filters match (name contains, email equals, label any-of, etc.).

---

## Phase 4 — Conversations + Messages

The highest-risk phase — conversation lifecycle touches nearly every
other subsystem. See detailed sub-plan under `PLAN.phase4.md` (created
when Phase 4 starts — not yet).

High-level chunks:
- Model: `Conversation` state machine (`pending`/`open`/`resolved`/
  `snoozed`), `Message` (`incoming`/`outgoing`/`activity`/`template`),
  `Attachment`, `Mention`, `Notification`.
- Service: AutoAssignment (round-robin), Reopen on new incoming,
  ResolveWithCsat, AssignTeam, SetPriority, SLA tick.
- Realtime: replicate ActionCable channel names (
  `RoomChannel` / `user-<id>` / `conversation-<uuid>`) over FastAPI
  WebSockets + Redis pub/sub. Payload shape must match so existing
  Chatwoot frontend could theoretically talk to AloStudio.
- Jobs: ConversationAutoResolutionJob, RoundRobinAssignmentJob,
  ConversationReplyMailer, NotificationDispatchJob.

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
