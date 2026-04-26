# Phase 4c — Conversations + Messages: assignment

**Why split from 4b:** 4b shipped realtime + activity messages. 4c
ports the assignment-routing layer Chatwoot calls "auto-assignment v1"
(round-robin per inbox) plus the role-based view scoping that gates
agent visibility on every conversation list.

**Reference anchors (verbatim paths under `reference/chatwoot/`):**

* `app/services/conversations/permission_filter_service.rb`
* `app/services/auto_assignment/agent_assignment_service.rb`
* `app/services/auto_assignment/inbox_round_robin_service.rb`
* `app/services/auto_assignment/round_robin_selector.rb`
* `app/models/concerns/auto_assignment_handler.rb`
* `app/models/concerns/assignment_handler.rb` (already partially ported
  in 4b.3 via `update_team`'s `ensure_assignee_is_from_team` guard).

The Chatwoot v2 ("Assignment V2") track is enterprise-feature-gated
(`account.feature_enabled?('assignment_v2')`) and uses background jobs
to redistribute capacity. We port v1 only — same API surface, simpler
implementation, sufficient for parity.

---

## Milestones

Each milestone ships in its own commit. Tests stay green after every
commit.

### 4c.1 — PermissionFilterService

Inject the role-based scope into both `conversation_finder` and
`conversation_filter`:

* Administrators see every conversation in the account.
* Agents see only conversations whose `inbox_id` is in
  `inbox_members.where(user_id=current_user)` for the active account.

**Tasks:**
- [ ] `app/domains/conversations/permission.py` — single
      `apply_permission_scope(stmt, *, account_id, current_user_id)`
      function that adds the `WHERE inbox_id IN (...)` clause for
      non-admins.
- [ ] Wire it into `finder.py` + `filter.py` so the index / search /
      filter endpoints all honor the scope.
- [ ] Integration tests: agent sees only their inbox's conversations,
      admin sees everything.

### 4c.2 — Round-robin queue + AgentAssignmentService

Redis-backed FIFO queue per inbox. Pop the head of the intersection
between `queue` and `allowed_agent_ids`, push it back at the tail.

**Tasks:**
- [ ] `app/core/round_robin.py` — thin wrapper over `redis.asyncio`
      with `lpush` / `lrange` / `lrem` matching the Ruby
      `Redis::Alfred` interface. Key format
      `ROUND_ROBIN_AGENTS::<inbox_id>`.
- [ ] `app/domains/auto_assignment/round_robin.py` —
      `InboxRoundRobinService` port (reset_queue, available_agent,
      add/remove_agent_from_queue).
- [ ] `app/domains/auto_assignment/agent_assignment.py` —
      `AgentAssignmentService.find_assignee` / `perform`. Uses the
      round-robin queue intersected with `allowed_agent_ids`.
- [ ] Online-agent filtering deferred — `OnlineStatusTracker` lands
      with the presence heartbeat (4b.7 stretch / 4c follow-up). The
      service falls back to "every member is candidate" until then.
- [ ] Hook InboxMember create/destroy to update the queue (mirrors
      Rails `after_create_commit` / `after_destroy_commit` on
      `InboxMember`).
- [ ] Unit tests against a fake Redis (existing `_StubRedis` from
      4b.1).

### 4c.3 — AutoAssignmentHandler wiring

Trigger `AgentAssignmentService.perform` from the right service paths:

* `create_conversation` — when no `assignee_id` is supplied, the
  inbox has `enable_auto_assignment=True`, and an inbox member exists.
* `update_team` — when the new team has `allow_auto_assign=True` and
  the assignee was cleared (or absent), pick from team∩inbox.
* `toggle_status` — when status flips back to `open` and the assignee
  is now blank or no longer an inbox member, re-run.

**Tasks:**
- [ ] `app/domains/conversations/auto_assignment.py` — single
      `maybe_run_auto_assignment(session, *, conversation)` function.
- [ ] Hook into the three service paths above. `update_team` already
      has the team-scope assignee guard from 4b.3; add the round-robin
      replacement.
- [ ] Activity message: when the round-robin picks an assignee, the
      assignee-change activity row should fire with `user_name = nil`
      (Rails uses the system actor — we'll emit
      `Conversation assigned to <agent> by Chatwoot`-style content via
      the existing `_current_user_name()` fallback).
- [ ] Integration tests: new conv on auto-assign inbox lands on a
      member; second conv lands on the next member; full rotation.

### 4c.4 — Tests + parity + PLAN update

- [ ] Parity tests for `/assignments` cross-backend auth gates already
      exist (4b.6) — keep them. Add the round-robin happy-path as a
      pure-integration test (parity is hard without a seeded Chatwoot
      Redis).
- [ ] Update `PLAN.md` to mark 4c done.

---

## Deferred

* `Assignment V2` (`AutoAssignment::AssignmentJob`) — needs the
  feature-flag store + the rebalance algorithm. Phase 7 alongside the
  other enterprise toggles.
* `OnlineStatusTracker` — presence heartbeat on `RoomChannel`. Lands
  with whichever phase ports `update_presence`.
* `RoundRobinSelector` capacity-aware variant — adds load balancing
  on top of FIFO. Same phase as Assignment V2.
* AgentBot assignment branch in `/assignments` — Phase 8.

---

## Commit style

`phase4c: <area>: <short summary>` — one commit per milestone.
