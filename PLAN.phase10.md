# Phase 10 — Hardening

**Why this phase:** The previous nine phases shipped the wire surface;
Phase 10 makes it operationally ready. Three things land here:

  1. **Runtime services** the dashboard already references but that
     were deferred from earlier phases — the campaign scheduler,
     snoozed-conversation reopener, and the public Help Center surface.
  2. **Observability** so the running stack is debuggable in
     production — request-id correlation, structured logging fields,
     a meaningful `/health` payload.
  3. **Parity schema sweep** for the enterprise-only tables we logged
     as deferred (audits, sla_policies, applied_slas) so a future
     enterprise reactivation doesn't need another migration.

**Reference anchors:**

* `app/jobs/trigger_scheduled_items_job.rb` (the 5-min cron)
* `app/jobs/campaigns/trigger_oneoff_campaign_job.rb`
* `app/jobs/conversations/reopen_snoozed_conversations_job.rb`
* `app/controllers/public/api/v1/portals_controller.rb` + nested
* `config/schedule.yml`

---

## Scope decisions

**In scope:**
  * **ARQ worker + scheduler** — periodic 5-min job that fires
    one_off campaigns due in the [now − 3d, now] window and reopens
    snoozed conversations whose ``snoozed_until`` has passed. ARQ
    was already added to deps in Phase 0 but never wired.
  * **Public Help Center** — read-only surface
    (``GET /hc/<slug>``, ``GET /hc/<slug>/articles``,
    ``GET /hc/<slug>/categories``). Mirrors
    ``reference/chatwoot/app/controllers/public/api/v1/portals_controller.rb``.
  * **Observability** — request id correlation via middleware,
    structured-log binding on every router, ``/health`` returns DB
    + Redis ping + uptime.
  * **Schema sweep** for enterprise-deferred tables: `audits`,
    `sla_policies`, `applied_slas`. Tables only — controllers/policies
    stay enterprise.

**Deferred (out of v4.13.0 OSS parity scope):**
  * Per-vendor integration adapters (Slack OAuth, Dialogflow,
    OpenAI, etc.) — each its own follow-up.
  * Sentry / OpenTelemetry wire — observability scaffold lands but
    third-party exporter wiring is deployment-specific.
  * Real-DB import from a running Chatwoot Postgres dump — the
    schema is byte-parity by design so any pg_dump → pg_restore
    works; we don't ship a bespoke importer.
  * Cryptography uplift (encrypts :access_token on integrations
    hooks) — needs Rails-compatible Active Record Encryption shim;
    defer until a customer needs it.

## Test strategy

  * **Unit** — scheduler tick semantics + structured-log field
    population.
  * **Integration** — public Help Center surface, scheduler runs
    against a seeded campaign.
  * **Parity** — 401-on-no-auth across the new endpoints (the
    public Help Center is no-auth by design; we pin its 200 + 404
    shapes against the reference).

---

## Milestones

### 10.1 — ARQ worker + scheduler

**Tasks:**
- [x] `app/workers/__init__.py` + `app/workers/scheduler.py` —
      ARQ ``WorkerSettings`` with the 5-min ``cron`` task that
      mirrors ``TriggerScheduledItemsJob``.
- [x] Job: fire one_off campaigns due in the window, marking each
      as ``campaign_status=completed`` once fired.
- [x] Job: reopen snoozed conversations whose
      ``snoozed_until <= now()``.
- [x] Tests: scheduler runs against seeded state, mutates correctly.

### 10.2 — Public Help Center surface

**Tasks:**
- [x] `app/domains/portals/public_router.py` — read-only endpoints:
      * ``GET /hc/<slug>``
      * ``GET /hc/<slug>/articles[?locale=]``
      * ``GET /hc/<slug>/categories[?locale=]``
- [x] Only ``status=published`` articles surface on the public side.
- [x] Per-locale filtering.
- [x] Tests: published articles visible; drafts hidden; unknown slug
      → 404; locale filter works.

### 10.3 — Observability

**Tasks:**
- [x] Request-id middleware that reads/creates ``X-Request-Id`` and
      binds it onto the structured-log context (matches Rails'
      ``ActionDispatch::RequestId``).
- [x] Beef up ``/health``: DB ping, Redis ping, uptime, version.
- [x] Add ``performer.id`` / ``account_id`` to log context when
      ``account_context`` resolves.
- [x] Tests: middleware sets the header, ``/health`` carries the
      live components.

### 10.4 — Enterprise-deferred schema sweep

**Tasks:**
- [x] Migration only — no service/router code:
      * ``audits`` table (auditable_id/type, user_id/type, action,
        audited_changes JSONB, version, remote_address, request_uuid).
      * ``sla_policies`` table (name, description,
        first_response_time_threshold, next_response_time_threshold,
        resolution_time_threshold, only_during_business_hours,
        account_id).
      * ``applied_slas`` table (account/sla_policy/conversation +
        sla_status enum, UNIQUE composite index).
- [x] No SQLModel classes (defer to enterprise reactivation —
      tables alone are enough for pg_dump parity).
- [x] Test: alembic upgrade head produces the three tables.

### 10.5 — Parity tests + close Phase 10

- [x] Parity 200/404 shape on `/hc/<slug>` against the reference.
- [x] Parity 401 across the auth-gated endpoints we still haven't
      pinned (any leftovers).
- [x] Mark Phase 10 done + roll up the all-phase summary in PLAN.md.

---

## Commit style

`phase10.<n>: hardening: <short summary>` — one commit per milestone.
