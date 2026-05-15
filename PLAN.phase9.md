# Phase 9 — Admin advanced

**Why this phase:** Closes the admin-side surface so an account
operator can configure working hours, set SLA policies, manage a
help-center portal, run campaigns and audit who did what. Phase 7's
``value_in_business_hours`` column finally becomes meaningful once
working-hours config lands.

**Reference anchors (verbatim paths under `reference/chatwoot/`):**

* `app/models/working_hour.rb` + `app/controllers/api/v1/accounts/working_hours_controller.rb`
* `app/models/sla_policy.rb` + `app/models/applied_sla.rb`
* `app/models/portal.rb` + `app/models/article.rb` + `app/models/category.rb`
* `app/controllers/api/v1/accounts/portals_controller.rb` +
  `articles_controller.rb`
* `app/models/campaign.rb` +
  `app/controllers/api/v1/accounts/campaigns_controller.rb`
* `app/models/audit.rb` (audited gem table)

---

## Scope decisions

**In scope:**
  * **Working hours** — per-inbox weekly schedule (7 rows, one per
    day) + ``timezone`` column on inbox. Powers Phase 7's
    ``value_in_business_hours`` computation.
  * **SLA policies** — model + CRUD; ``AppliedSla`` rows when a
    policy is attached to a conversation; first-response /
    next-response / resolution time targets.
  * **Portal + Article + Category** — Help Center surface (CRUD only
    on dashboard side; public read endpoints defer with the Phase 5a
    follow-up).
  * **Campaigns** — one_off + ongoing campaign CRUD;
    delivery_status enum; no scheduler runtime (Phase 10 hardening).
  * **Audit log read endpoint** — `GET /audits` so dashboards can
    show recent activity. We do NOT ship a per-model
    ``after_save`` audit emitter (the ``audited`` gem behaviour is
    pervasive and parity-noisy); audits get written by the few
    paths the dashboard surfaces explicitly (Phase 9 follow-up).

**Deferred:**
  * Custom roles (enterprise-only).
  * Campaign scheduler runtime (ARQ-backed; lands with Phase 10).
  * Audit-trail emitter for every mutating action (Phase 10
    hardening).
  * Public Help Center surface (`/hc/<slug>` pages) — companion to
    Phase 5a's widget. Phase 9 ships the dashboard CRUD only.
  * Working-hours daylight-saving conversions across timezones —
    we use the timezone string verbatim, deferring DST edge-case
    audits to Phase 10.

## Test strategy

Same as Phase 7/8: integration on real Postgres, parity 401-gate
tests across the new endpoints.

---

## Milestones

### 9.1 — Working hours

**Tasks:**
- [x] `WorkingHour` SQLModel + Alembic migration
      (id, inbox_id, account_id, day_of_week 0-6, open_hour,
      open_minutes, close_hour, close_minutes, closed_all_day,
      open_all_day, timezone). The ``timezone`` column lives on the
      inbox too — add via the Phase 2 inbox migration follow-up if
      missing.
- [x] CRUD `PATCH /api/v1/accounts/{id}/inboxes/{iid}/working_hours`
      (bulk update of all 7 rows).
- [x] Toggle `working_hours_enabled` on inbox.
- [x] Re-wire Phase 7.1's reporting listener to honour the inbox's
      working hours when computing ``value_in_business_hours``.
- [x] Tests: CRUD + business-hours computation cases.

### 9.2 — SLA policies (DEFERRED — enterprise-only)

After surveying the reference, ``SlaPolicy`` and ``AppliedSla`` live
in ``reference/chatwoot/enterprise/`` — the controller, model and
policy are all enterprise-gated. The DB schema includes the tables
(both distributions share the schema) but the API surface is not
OSS parity.

We **defer** SLA from Phase 9. The schema columns + tables land
with Phase 10 hardening's parity schema sweep so a future
enterprise-side reactivation doesn't need another migration.

### 9.3 — Portal + Article + Category

**Tasks:**
- [x] `Portal` + `Article` + `Category` SQLModels + Alembic migration.
- [x] CRUD `/api/v1/accounts/{id}/portals` (admin-only).
- [x] CRUD `/api/v1/accounts/{id}/portals/{slug}/articles`.
- [x] CRUD `/api/v1/accounts/{id}/portals/{slug}/categories`.
- [x] Tests.

### 9.4 — Campaigns

**Tasks:**
- [x] `Campaign` SQLModel + Alembic migration
      (display_id, title, description, message, inbox_id,
      audience JSONB, scheduled_at, campaign_status, campaign_type,
      trigger_rules JSONB, account_id).
- [x] CRUD `/api/v1/accounts/{id}/campaigns` (admin-only).
- [x] Display_id sequence per account (Postgres BEFORE INSERT trigger).
- [x] Tests.

### 9.5 — Audit log read endpoint (DEFERRED — enterprise-only)

Same posture as 9.2 SLA: ``AuditLogsController`` lives in
``reference/chatwoot/enterprise/`` not OSS. The ``audits`` table
(provided by the ``audited`` gem) is shared schema but the read
endpoint is enterprise-gated.

We **defer** the audit log read endpoint from Phase 9. The
``audits`` table lands with Phase 10's parity schema sweep.

### 9.6 — Parity tests + close Phase 9

- [x] Stateless 401 parity across every new endpoint.
- [x] Mark Phase 9 done in PLAN.md.

---

## Commit style

`phase9.<n>: admin: <short summary>` — one commit per milestone.
