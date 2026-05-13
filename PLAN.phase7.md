# Phase 7 — Reports

**Why this phase:** Dashboards consume aggregate metrics over the
ConversationEvent/Message rows produced by Phases 4-6. Phase 7 ships
the reporting backbone: a `ReportingEvent` row per significant
state-change (resolve, first reply, reply latency, reopen) plus the
HTTP surfaces that compute summaries, timeseries and live counts
over those rows.

**Reference anchors (verbatim paths under `reference/chatwoot/`):**

* `app/models/reporting_event.rb`
* `app/listeners/reporting_event_listener.rb`
* `app/controllers/api/v2/accounts/reports_controller.rb`
* `app/controllers/api/v2/accounts/summary_reports_controller.rb`
* `app/controllers/api/v2/accounts/live_reports_controller.rb`
* `app/services/v2/reports/conversations/report_builder.rb`
* `app/services/v2/reports/conversations/metric_builder.rb`
* `app/services/v2/report_builder.rb`

---

## Scope decisions

Chatwoot's reports surface is enormous — 13 endpoints under
`/api/v2/accounts/{id}/reports` plus 5 summary endpoints plus 2 live
endpoints. We ship the parity-critical core that dashboards consume
in v4.13.0 and defer the rest:

**In scope:**
  * `ReportingEvent` model + listener firing on `conversation_resolved`,
    `conversation_opened`, `first_reply_created`, `reply_created` events.
  * `GET /api/v2/accounts/{id}/reports/summary` — the dashboard cards
    (conversations_count, incoming/outgoing message counts, resolution
    + first-response + reply averages).
  * `GET /api/v2/accounts/{id}/reports?metric=X&type=...` — the
    timeseries endpoint feeding the dashboard's line chart.
  * `GET /api/v2/accounts/{id}/reports/conversations` — current-state
    metric snapshot (`type=conversation` only).
  * `GET /api/v2/accounts/{id}/live_reports/conversation_metrics`
    — live counters (open, unattended, etc.).
  * `GET /api/v2/accounts/{id}/live_reports/grouped_conversation_metrics`
    — per-agent live counters.
  * `GET /api/v2/accounts/{id}/summary_reports/{agent,team,inbox,label}`
    — per-entity summaries used by the agent-performance widgets.

**Deferred (logged in PLAN, not in Phase 7):**
  * CSV renderers for agents/inboxes/labels/teams reports (Phase 7
    ships JSON; CSV is a renderer concern that needs the v4.13.0
    Jbuilder→CSV template pipeline; lands with Phase 7 follow-up or
    Phase 10 export plumbing).
  * `bot_summary` / `bot_metrics` / `conversation_bot_handoff` /
    `conversation_bot_resolved` events — these need agent-bot infra
    (Phase 8).
  * `year_in_review` — promotional one-shot.
  * `conversation_traffic` heatmap — timezone-heavy, defer.
  * `inbox_label_matrix` — cross-tab, defer.
  * `first_response_time_distribution` — histogram bucket, defer.
  * `outgoing_messages_count` — defer with the other group_by reports.
  * `summary_reports/channel` — needs channel-type aggregation; can
    live alongside our channel-type registry later.
  * `reporting_events_rollups` table + RollupService — performance
    optimisation, not parity-critical. We compute on-demand from raw
    `reporting_events` rows.
  * Captain (AI assistant) inference events — Phase 8.

## Test strategy

Three tiers as always:
  * **Unit** — date-range arithmetic, metric aggregation helpers.
  * **Integration** — full-stack: seed conversations/messages, trigger
    state transitions, assert ReportingEvent rows + endpoint JSON.
  * **Parity** — auth gates + body-shape locks against the running
    reference. Happy-path body parity needs synchronised seed data
    so we stay on stateless surfaces (consistent with the rest of
    the parity tier).

---

## Milestones

### 7.1 — ReportingEvent foundation + listener

**Tasks:**
- [ ] `ReportingEvent` SQLModel + Alembic migration matching
      `reference/chatwoot/db/schema.rb`'s `reporting_events` table.
- [ ] Listener firing on the dispatcher events:
      `conversation_resolved` → `conversation_resolved` event (value =
      seconds from create to resolve).
      `first_reply_created` → `first_response` event (value =
      seconds from last contact activity to first agent reply).
      `reply_created` → `reply_time` event (value = seconds from
      `waiting_since` to reply).
      `conversation_opened` → `conversation_opened` event (value =
      seconds since last resolve, or 0 first-time).
- [ ] `value_in_business_hours` defaults to `value` when the inbox
      doesn't have working hours configured (working-hours table
      lands in Phase 9, so 7.1 treats every inbox as 24/7).
- [ ] Tests: each transition emits the right event with sane values;
      first-time-opened emits value=0; reopen emits time-since-resolve.

### 7.2 — Summary report (the dashboard cards)

**Tasks:**
- [ ] `GET /api/v2/accounts/{id}/reports/summary` —
      returns `{conversations_count, incoming_messages_count,
      outgoing_messages_count, avg_first_response_time,
      avg_resolution_time, reply_time, resolutions_count,
      previous}`. The `previous` block re-runs the same query with
      the symmetric prior window.
- [ ] `GET /api/v2/accounts/{id}/reports/conversations?type=conversation`
      — returns `{open, unattended_count, unassigned_count}`.
- [ ] Tests: seed a known set of events + conversations, assert each
      metric.

### 7.3 — Timeseries report

**Tasks:**
- [ ] `GET /api/v2/accounts/{id}/reports?metric=...&type=...&since=&until=`
      — returns daily buckets `[{value, timestamp}, ...]`.
      Metrics: `conversations_count`, `incoming_messages_count`,
      `outgoing_messages_count`, `avg_first_response_time`,
      `avg_resolution_time`, `reply_time`, `resolutions_count`,
      `bot_resolutions_count` (no-op until Phase 8),
      `bot_handoffs_count` (ditto), `customer_satisfaction_score`.
- [ ] Date buckets honour `timezone_offset` (degrees-of-UTC float
      from the dashboard).
- [ ] Tests: cover the metric-name dispatch + bucket math.

### 7.4 — Live reports

**Tasks:**
- [ ] `GET /live_reports/conversation_metrics` — current snapshot:
      `{open, unattended_count, unassigned_count, all_count}`.
- [ ] `GET /live_reports/grouped_conversation_metrics?type=Agent` —
      per-agent breakdown: `[{user_id, open, unattended_count, ...}]`.
- [ ] Tests: state-transition affects counts.

### 7.5 — Per-entity summary reports

**Tasks:**
- [ ] `GET /summary_reports/agent` — per-agent metric tuple.
- [ ] `GET /summary_reports/team` — per-team.
- [ ] `GET /summary_reports/inbox` — per-inbox.
- [ ] `GET /summary_reports/label` — per-label.
- [ ] Tests for each grouping.

### 7.6 — Parity tests + close Phase 7

- [ ] Stateless 401-on-no-auth parity for each endpoint surface
      (same posture as Phase 6's parity tier).
- [ ] Mark Phase 7 done in PLAN.md.

---

## Commit style

`phase7.<n>: reports: <short summary>` — one commit per milestone.
