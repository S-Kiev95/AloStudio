# Phase 6 — Automation + Macros + Labels + CSAT

**Why this phase:** Channel cluster (5a→5g) is closed; every event
that automation reacts to (incoming, outgoing, status_change,
conversation_created, conversation_updated, message_created) now
emits in production. Phase 6 layers the rule engine + manual
playbooks (macros) + CSAT survey on top.

**Reference anchors (verbatim paths under `reference/chatwoot/`):**

* `app/models/label.rb` (+ `acts_as_taggable_on` polymorphic taggings)
* `app/controllers/api/v1/accounts/labels_controller.rb`
* `app/jobs/labels/update_job.rb`
* `app/models/macro.rb`
* `app/controllers/api/v1/accounts/macros_controller.rb`
* `app/services/macros/execution_service.rb`
* `app/models/automation_rule.rb`
* `app/services/automation_rules/{action_service,condition_validation_service,conditions_filter_service}.rb`
* `app/listeners/automation_rule_listener.rb`
* `app/controllers/api/v1/accounts/automation_rules_controller.rb`
* `app/models/csat_survey_response.rb`
* `app/controllers/api/v1/accounts/csat_survey_responses_controller.rb`
* `app/controllers/public/api/v1/csat_survey_controller.rb`

---

## Scope decisions

* **Labels are already half-built.** The `Label` model and
  `ConversationLabel` join landed in Phase 4a so `update_labels`
  could write through them. 6.1 only ships the CRUD router + the
  rename cascade (`Labels::UpdateJob` equivalent).
* **Operator set for AutomationRule conditions:** ship the full
  Chatwoot operator set (`equal_to`, `not_equal_to`, `contains`,
  `does_not_contain`, `is_present`, `is_not_present`,
  `greater_than`, `lesser_than`, `is_greater_than`, `is_less_than`,
  `starts_with`) — the engine isn't useful with a subset since
  imported rules from Chatwoot would silently no-op.
* **Action set for AutomationRule:** ship the parity-critical core —
  `assign_team`, `assign_agent`, `add_label`, `remove_label`,
  `change_priority`, `change_status`, `send_email_transcript`,
  `send_message`, `send_attachment`, `mute_conversation`,
  `snooze_conversation`, `resolve_conversation`. The webhook +
  Slack-message actions defer to Phase 8 (Integrations).
* **CSAT** survey rides the public widget surface (5a). The agent
  dashboard's metrics + download endpoints ride 6.5 alongside the
  trigger.
* **Campaigns** (`one_off` / `ongoing`) live in Phase 9 (admin
  advanced) — not part of Phase 6.

## Test strategy

* **Integration:** services tested against real Postgres; rule engine
  evaluation tested with synthesised conversations + messages.
* **Parity:** label CRUD body shape, macro execution, rule eval
  outcome (status flip / label add) verified against Chatwoot
  reference where the path is reachable without seed-data sync.

---

## Milestones

### 6.1 — Label CRUD + rename cascade

**Tasks:**
- [ ] `app/domains/labels/service.py` — create / update / destroy with
      title-rename cascade (when `title` changes, walk every
      `Conversation` whose `cached_label_list` includes the old title
      and rewrite the CSV).
- [ ] `app/domains/labels/router.py` — `GET/POST /api/v1/accounts/{id}/labels`
      + `GET/PATCH/DELETE /api/v1/accounts/{id}/labels/{id}`.
- [ ] Presenter parity with `_label.json.jbuilder` (id/title/
      description/color/show_on_sidebar).
- [ ] Tests: CRUD happy paths, title-uniqueness 422, rename cascade
      walks `cached_label_list`, label list shows up on conversation
      after rename.

### 6.2 — Macro: model + CRUD + executor

**Tasks:**
- [ ] `Macro` SQLModel — `(account_id, name, actions JSONB,
      visibility, created_by_id, updated_by_id)`. Visibility enum:
      `personal` / `global`.
- [ ] Alembic migration.
- [ ] CRUD endpoints — `/api/v1/accounts/{id}/macros` (index/show/
      create/update/destroy/copy/execute).
- [ ] `app/domains/macros/execution.py` — apply each action JSON
      verbatim, dispatching to the same action handlers the
      AutomationRule action_service uses (so 6.3's executor can lean
      on this directly).
- [ ] Tests: CRUD, execution applies labels + status + priority,
      `copy` clones into the caller's account.

### 6.3 — AutomationRule: model + condition evaluator + action executor

**Tasks:**
- [ ] `AutomationRule` SQLModel — `(account_id, name, description,
      event_name, conditions JSONB, actions JSONB, active)`.
- [ ] Alembic migration.
- [ ] `app/domains/automation/conditions.py` — operator dispatch
      (`equal_to`, `not_equal_to`, `contains`, `does_not_contain`,
      `is_present`, `is_not_present`, `greater_than`, `lesser_than`,
      `is_greater_than`, `is_less_than`, `starts_with`).
- [ ] `app/domains/automation/actions.py` — shared action executor
      reused by Macro.
- [ ] CRUD endpoints, `clone`, `attach_file` for the
      `send_attachment` action.
- [ ] Tests: condition matrix per operator, action execution end-to-end.

### 6.4 — AutomationRule listeners (event hooks)

**Tasks:**
- [ ] Hook the rule engine into the dispatcher events from Phase 4b:
      `CONVERSATION_CREATED`, `CONVERSATION_UPDATED`, `MESSAGE_CREATED`.
- [ ] Map dispatcher event -> AutomationRule.event_name allow-list
      (Chatwoot's `EVENTS` constant).
- [ ] Per-event filter: `event_name` matches → evaluate conditions →
      execute actions.
- [ ] Idempotency: skip rules that already fired on this conversation
      for events with `re_run` semantics off (matches Rails'
      `processed_for_event` audit).
- [ ] Tests: synthesised payload through dispatcher triggers rule;
      negative path (condition fails) produces no action.

### 6.5 — CSAT survey

**Tasks:**
- [ ] `CsatSurveyResponse` SQLModel — `(account_id, conversation_id,
      message_id, rating, feedback_message, contact_id, assigned_agent_id)`.
- [ ] Alembic migration.
- [ ] Dashboard endpoints — `index`, `metrics`, `download` (CSV).
- [ ] Public response endpoint — `PUT /public/api/v1/csat_survey/{uuid}`.
- [ ] Trigger: when conversation resolves, fire the
      "send_message" action with content_type `input_csat` if the
      inbox has CSAT enabled.
- [ ] Tests: response submit creates row, metrics aggregation
      counts ratings, trigger fires on resolve.

### 6.6 — Parity tests + close Phase 6

- [ ] Cross-backend parity for Label CRUD body shape.
- [ ] Macro execution outcome parity.
- [ ] Update `PLAN.md` to mark Phase 6 done.

---

## Commit style

`phase6: <area>: <short summary>` — one commit per milestone, same
shape as 5a-5g.
