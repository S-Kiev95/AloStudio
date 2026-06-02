# PLAN.frontend-v2 — closing functional parity with Chatwoot

**Goal.** Take the AloStudio frontend from "v1 = common-flow parity"
(merged on `main` as of commit `9267143`) to **full functional parity**
with Chatwoot OSS v4.13.0 for what a real customer needs day-to-day,
and tighten the MCP + webhook surface so an external AI agent can
plug in cleanly.

**What "complete" means for v2.** The remaining honest gaps flagged in
[`PLAN.parity-review.md`](PLAN.parity-review.md) §1–§8 close. After v2
the only outstanding items are explicitly out-of-scope (enterprise,
billing, Captain AI, SLA, article embeddings, file uploads) plus the
power-user backlog in [`PLAN.parity-review.md §12`](PLAN.parity-review.md).

**Why now.** The MCP server is done and stable. The user is building an
agent in a separate Claude Code account that will consume it. Once v2
closes, the dashboard reaches a state worth auditing with Claude 4.8
(backend audit → frontend audit) before any UI-polish pass.

**Layout of the plan.** Sub-milestones come in two clusters:

* **v2.1–v2.6 — human-side parity** (Contacts, Agents+Profile+Security,
  Notifications inbox). What a human operator misses today vs Chatwoot.
* **v2.7–v2.9 — AI-agent integration polish** (HTTP MCP transport,
  webhook event_id + signature header alias + `sender_type`,
  `ai_mode` to prevent self-loops, ARQ-backed delivery retries). Sharper-
  edge improvements surfaced by the external agent ("Alicia") trying to
  consume the MCP + webhooks the v1 backend already exposes.

---

## Branch strategy

* `main` — stable; v1 lives here (commit `9267143`).
* `feat/v2` — new working branch for everything in this plan. Created
  from `main`. Merged back to `main` with `--no-ff` when v2 closes
  (same shape as the v1 merge).
* Backend-first sub-milestones land on `main` directly (small, focused,
  test-covered) and `feat/v2` rebases to pick them up. Same dance we
  ran for the MCP tokens admin router and the public article-by-slug
  endpoint during v1.

```
main ─── v1 merge (9267143) ─── be.agents ─── be.notifications ─── v2 merge
                              ↘                ↘                  ↗
                              feat/v2 ─── fe.14a ── … ── fe.14d ─┘
```

---

## Milestones

Ordered by **value per session** — by the end of fe.14b the largest
visible gap (no Contacts) is closed; by fe.14c the product is usable
multi-agent; fe.14d is the last polish before the audit.

### v2.1 — `fe.14a` Contacts: list + search + create + detail

**Backend:** ✅ already ported. `app/domains/contacts/router.py` exposes:

* `GET    /api/v1/accounts/{id}/contacts` — list
* `GET    /api/v1/accounts/{id}/contacts/search`
* `POST   /api/v1/accounts/{id}/contacts`
* `GET    /api/v1/accounts/{id}/contacts/{cid}`
* `PATCH  /api/v1/accounts/{id}/contacts/{cid}`
* `DELETE /api/v1/accounts/{id}/contacts/{cid}`
* `GET    /api/v1/accounts/{id}/contacts/{cid}/contactable_inboxes`
* `GET    /api/v1/accounts/{id}/contacts/{cid}/notes` (CRUD)
* `POST   /api/v1/accounts/{id}/contacts/{cid}/destroy_custom_attributes`
* `POST   /api/v1/accounts/{id}/contacts/{cid}/contact_inboxes`

**Frontend deliverables:**

* `lib/api/contacts.ts` — types + hooks (`useContacts`, `useContact`,
  `useSearchContacts`, `useCreateContact`, `useUpdateContact`,
  `useDeleteContact`, `useContactNotes`, `useCreateNote`, etc.).
* `components/contacts/contacts-view.tsx` — list with search bar,
  pagination, create button.
* `components/contacts/contact-form.tsx` — name, email, phone, company,
  custom attributes (read from `useCustomAttributes("contact_attribute")`).
* `components/contacts/contact-detail-view.tsx` — header card + tabs:
  Información (form), Conversaciones (per-contact list), Notas,
  Contactable inboxes.
* `components/contacts/notes-panel.tsx` — inline note CRUD.
* Routes: `/contacts`, `/contacts/new`, `/contacts/[id]`.
* Main sidebar nav: add "Contactos" between Conversaciones and
  Instagram.
* Test: contacts-view list + 1 helper round-trip.

**Definition of done:** I can create a contact via the UI, find them
via search, edit their custom attributes, add a note, and see which
inboxes I can message them on.

---

### v2.2 — `fe.14b` Contact merge + inline panel in conversation detail

**Backend:** ✅ ported.

* `POST /api/v1/accounts/{id}/actions/contact_merge` — backend
  `app/domains/contacts/router.py:510` (`actions_router`). Merges two
  contacts; the loser's conversations + notes + attributes move to
  the winner.

**Frontend deliverables:**

* `components/contacts/merge-dialog.tsx` — invoked from the contact
  detail view. Search-picker for the contact to merge into, confirmation
  step ("X conversations + Y notes will move to <winner>"), POST.
* `components/conversations/contact-panel.tsx` — the right-hand panel
  upstream Chatwoot shows next to the message thread. Surfaces:
  name + email + phone + avatar, custom attributes (inline editable),
  shared notes (link to the contact's notes page), previous
  conversations (last 5 with links), labels visible on this contact.
* Wire `contact-panel.tsx` into `conversation-view.tsx` as a
  collapsible side column (hidden on narrow viewports; sheet drawer
  on mobile).
* Tests: merge-dialog logic + contact-panel render.

**Definition of done:** Two test contacts can be merged via UI; the
losing contact's conversations now show under the winner. In the
conversation detail page, the contact info shows in a side panel
without leaving the thread.

---

### v2.3 — `be.agents` Agent invitations + AgentsController (backend)

**Status:** ❌ not ported. Needs a new domain.

**Backend deliverables** (all on `main` directly):

* `app/domains/agents/router.py` — admin-only:
  * `GET    /api/v1/accounts/{id}/agents` — list account members
    (decorated with `availability_status`).
  * `POST   /api/v1/accounts/{id}/agents` — invite a new member
    by email + role (`administrator` / `agent`). Creates the User
    if missing, the AccountUser link, mails the invitation.
  * `PATCH  /api/v1/accounts/{id}/agents/{aid}` — change role.
  * `DELETE /api/v1/accounts/{id}/agents/{aid}` — remove from
    account (`AccountUser.destroy`, not `User.destroy`).
* Existing `useAgents` hook in `account.ts` already hits this list
  endpoint — frontend will keep working when the backend lands.
* Devise invitable wiring (`User.invite!`) — generates a one-time
  token, sends email via the existing mailer.
* MailHog (already in `docker-compose.yml`) catches the dev emails;
  prod uses whatever SMTP `settings.SMTP_*` points at.
* Migration: confirm `invitation_token`, `invitation_sent_at` columns
  exist on `users` (Chatwoot has them via devise_invitable).
* Tests: invite flow happy path + 422 on duplicate + 401 from agent
  trying to invite + role demotion + remove member.

**Definition of done:** A pytest integration test posts an invite,
asserts the User+AccountUser rows are created, asserts an email lands
in MailHog with a working `invitation_token`.

---

### v2.4 — `fe.14c` Settings → Agents + Profile + Security (frontend)

**Backend:** ✅ after v2.3 lands. Profile already has GET/PUT in
`app/domains/users/router.py`.

**Frontend deliverables:**

* `lib/api/agents-admin.ts` — `useInviteAgent`, `useUpdateAgentRole`,
  `useRemoveAgent`. Existing `useAgents` already lists.
* `components/settings/agents/agents-view.tsx` — list with role badge
  (admin/agent), availability dot, last seen, invite + remove
  buttons. Invite form: email + role select.
* `lib/api/profile.ts` — client-side hook (currently only a
  `server-only` `getProfile` exists). Adds `useUpdateProfile`,
  `useChangePassword`.
* `components/settings/profile/profile-view.tsx` — name, available
  name, email, avatar URL.
* `components/settings/security/security-view.tsx` — change-password
  form, list of active sessions (if backend supports it; otherwise
  defer the sessions list).
* New sidebar entries in `settings-sidebar.tsx`:
  Agentes · Mi perfil · Seguridad (slot them above "Etiquetas").
* Routes: `/settings/agents`, `/settings/profile`, `/settings/security`.
* Tests: invite happy path, profile update.

**Definition of done:** I can invite a second user, they sign in via
the link in MailHog, they show up in the agents list. I can change my
own name + password from `/settings/profile` + `/settings/security`.

---

### v2.5 — `be.notifications` Notifications model + router (backend)

**Status:** ❌ not ported.

**Backend deliverables** (on `main`):

* `app/domains/notifications/models.py` — `Notification` SQLModel:
  `id`, `account_id`, `user_id`, `primary_actor_type`,
  `primary_actor_id`, `secondary_actor_type`, `secondary_actor_id`,
  `notification_type` (enum: conversation_assignment, mention,
  message, etc.), `read_at`, `created_at`. Mirrors Chatwoot.
* `app/domains/notifications/router.py`:
  * `GET    /api/v1/accounts/{id}/notifications` — list, paginated,
    optional `?status=unread`.
  * `POST   /api/v1/accounts/{id}/notifications/{nid}/read` — mark
    one read.
  * `POST   /api/v1/accounts/{id}/notifications/read_all` — mark all
    read.
  * `DELETE /api/v1/accounts/{id}/notifications/{nid}` — dismiss.
  * `GET    /api/v1/accounts/{id}/notification_settings` — per-user.
  * `PATCH  /api/v1/accounts/{id}/notification_settings`.
* `app/domains/notifications/listener.py` — subscribe to dispatcher
  events (`CONVERSATION_ASSIGNED`, `MENTION_CREATED`, etc.) and
  insert rows. Mirrors `notifications/listener.rb`.
* Cable channel emits `notification.created` so the bell badge
  updates without polling.
* Migration: `notifications` + `notification_settings` tables.
* Tests: listener fires on assign, list endpoint returns it, read
  endpoint flips `read_at`, cable emits the event.

**Definition of done:** Assigning a conversation to a user creates a
row in `notifications` for that user. The unread list returns it.
Marking it read sets `read_at`.

---

### v2.6 — `fe.14d` Notification bell + inbox + preferences (frontend)

**Backend:** ✅ after v2.5 lands.

**Frontend deliverables:**

* `lib/api/notifications.ts` — `useNotifications`, `useUnreadCount`
  (refetched via cable event), `useMarkNotificationRead`,
  `useMarkAllRead`, `useNotificationSettings`,
  `useUpdateNotificationSettings`.
* `components/shell/notification-bell.tsx` — bell icon in the
  topbar with red dot when `unread_count > 0`. Click opens a popover
  with the last 10 notifications.
* Popover row: actor name + notification kind + timestamp
  (`relativeTime`) + link to the relevant page (conversation /
  contact). "Marcar todas como leídas" link.
* `app/accounts/[accountId]/notifications/page.tsx` — full inbox
  view (paginated, filter unread/all).
* `components/settings/notification-prefs/notification-prefs-view.tsx`
  — toggle each notification type per channel (web / email).
  Sidebar entry "Notificaciones" in settings.
* Cable wiring: `use-cable.ts` invalidates `["notifications"]`
  on `notification.created` events.
* Tests: bell renders unread dot, popover list, mark-read flow.

**Definition of done:** When another agent assigns me a conversation,
my bell badge increments without me refreshing. Clicking the
notification lands me in the conversation.

---

## AI-agent integration polish (post-notifications)

The MCP server + outbound webhooks already exist (v1). When a second
Claude session started building an AI agent ("Alicia") that consumes
the MCP, it surfaced four sharp integration questions. The pieces
below close those gaps. They land *after* v2.5/v2.6 so the human-side
notifications surface ships first.

### v2.7 — `be.ai-integration-prep` (backend)

Lowest-hanging fixes. Roughly one focused session.

**Scope:**

* **HTTP MCP transport.** `app/mcp/README.md:101-106` documents
  `python -m app.mcp http --host 0.0.0.0 --port 8765` but the
  entry point isn't shipped — agents on a different host can only
  consume the MCP via stdio today. Add `app/mcp/__main__.py` that
  dispatches between `stdio` and `http` (streamable-http per fastmcp);
  same `build_server()` + `AuthMiddleware` instance for both.
* **`event_id` in the webhook body.** Today the per-delivery UUID
  lives in the `X-Chatwoot-Delivery` header
  (`app/domains/agent_bots/listener.py:135`). Mirror it into the
  JSON body so receivers can dedupe without parsing headers.
* **Dual signature header.** Today: `X-Chatwoot-Signature: <bare-hex>`
  (legacy Chatwoot parity). Emit *both*:
  `X-Chatwoot-Signature: <hex>` (kept for backward compat) **and**
  `X-AloStudio-Signature: sha256=<hex>` (the prefix form is what most
  modern receivers expect, GitHub-style). Same secret, same HMAC.
* **`sender_type` in message webhook body.** Resolve the STI on
  `Message.sender_type` (User / Contact / AgentBot / api) and emit
  it. Lets the receiver know who sent the message without an extra
  MCP round-trip.
* **`INTEGRATIONS.md` doc** at the repo root: payload shape (signed
  with examples), HMAC verification snippet, anti-loop guidance
  (*"filter on `message_type === \"incoming\"` — the webhook fires
  for both incoming and outgoing per Chatwoot parity"*), retry
  semantics (none today — see v2.9), and the auth model
  (Bearer token from `/settings/mcp_tokens`).

**Tests:**

* HTTP transport: integration test boots the MCP HTTP server in a
  thread, makes a real `Authorization: Bearer` call against it.
* Body fields: extend the existing webhook delivery tests to assert
  the new keys.
* Dual header: assert both headers appear, with matching hex digest.

**Definition of done:** Alicia (or any external agent) can do
*both* of these against a running AloStudio:
1. Open an MCP session over HTTP with a `write`-scope Bearer token,
   call `send_message`.
2. Stand up a webhook receiver, verify the `X-AloStudio-Signature`
   header, dedupe by `event_id`, and skip messages where
   `message_type === "outgoing"`.

### v2.8 — `be.ai-mode` (backend)

Mediano. Lets an AI agent "take over" a conversation and prevents
our own automation rules / macros from firing on top.

**Scope:**

* Migration: add `Conversation.ai_mode` (bool, default `false`) and
  optional `Conversation.ai_assignee` (string identifier of which
  AI took it, informational).
* Two new MCP tools in `app/mcp/tools/conversations.py`:
  * `get_ai_mode(conversation_id) -> {ai_mode, ai_assignee}`.
  * `set_ai_mode(conversation_id, on, ai_assignee?)` —
    scope=`write` required, fires a `conversation_updated` event so
    the human-side cable invalidates the cache.
* **Suppression hook:** automation rule listener
  (`app/domains/automation/listener.py`) skips when the conversation
  has `ai_mode=true`. Macros executed *manually* by a human agent
  are unaffected (the human knows what they're doing); macros chained
  *automatically* via an automation rule get skipped via the rule
  short-circuit.
* Optional: a `🤖 IA activa` badge in the conversation header on the
  frontend (could land as a follow-up — backend ships standalone).

**Tests:**

* `set_ai_mode(on)` flips the column and emits the cable event.
* Automation listener test: a rule that would otherwise fire skips
  when the conversation is in ai_mode.
* Permission test: a `read`-scope token can `get_ai_mode` but not
  `set_ai_mode`.

**Definition of done:** Alicia calls `set_ai_mode(conv, on=true)`,
takes over the conversation, our automation doesn't fight her. She
calls `set_ai_mode(conv, on=false)` when she hands back to a human.

### v2.9 — `be.webhook-retries` (backend)

Smallest-priority and largest-effort. Today
`app/domains/webhooks/listener.py:131-154` and
`app/domains/agent_bots/listener.py:277-305` deliver inline with a
10 s timeout and **no retries** — a non-2xx or transport error logs
and gives up.

**Scope:**

* Move webhook + agent-bot delivery to an ARQ job:
  `app/workers/jobs/deliver_webhook.py`.
* Exponential backoff: 4 retries at 5 s / 30 s / 5 min / 30 min,
  matching Chatwoot's `WebhookJob` `retry_on` config.
* Per-receiver dead-letter log (so an operator can see which
  receivers are misbehaving without reading the application log).
* Listener fan-out enqueues instead of calling `_deliver` directly.

**Tests:**

* Happy path: enqueue → ARQ worker runs → POST succeeds → no retry.
* Backoff: stub the HTTP client to return 500 twice then 200,
  assert 3 attempts spread across the schedule.
* Dead-letter: 5xx forever → row in the dead-letter table after
  the 4th retry exhausts.

**Definition of done:** A receiver that 500s once recovers without
human intervention; a receiver that 500s forever gets quarantined
and the operator has visibility.

---

## Out of scope for v2 (explicit defer)

Mirroring `PLAN.parity-review.md §13`:

* **SaaS billing** — not relevant self-hosted.
* **Enterprise tiers** (audit logs, custom roles, SSO sometimes) —
  defer indefinitely.
* **Captain AI** — conceptually overlaps with our MCP server. If we
  want it later, it's a separate v3 conversation.
* **SLA / Assignment policy** — backend not ported.
* **Article embeddings (pgvector)** — backend Phase 10 territory.
* **File uploads** (article images, agent avatars) — needs
  ActiveStorage equivalent on the backend; MinIO is in Docker but
  not wired.
* **Bulk conversation actions, saved views, full message search** —
  power-user features documented in
  [`PLAN.parity-review.md §12`](PLAN.parity-review.md) as the
  quick-win backlog. Not blockers for "complete".

---

## Definition of done for v2

After all 9 sub-milestones land and v2 merges to `main`:

* [ ] **`PLAN.parity-review.md`** updates: every `⚠️ Contacts` /
      `⚠️ Notifications` / `⚠️ Agents` flips to `✅`. The remaining
      `⚠️` entries are *all* power-user items in §12, none blocking.
* [ ] **Tests** — Vitest stays green, Playwright e2e gets at least
      one new spec per major surface (`contacts.spec.ts`,
      `agents-invite.spec.ts`, `notifications.spec.ts`). Backend
      pytest stays green; new integration tests cover the MCP HTTP
      transport, dual signature header, and ai_mode suppression.
* [ ] **DEPLOY.md** — extend with the MCP HTTP transport recipe
      (port + reverse-proxy notes). Vercel/Docker frontend section
      unchanged.
* [ ] **INTEGRATIONS.md** lands at the repo root, documenting the
      MCP + webhook contract for external AI agents (Alicia and
      whatever else plugs in).
* [ ] **Human smoke check**: log in → invite a teammate → they sign
      in → I assign them a conversation → their bell badge
      increments → they see the contact panel inline → they reply →
      I get a notification back.
* [ ] **AI smoke check**: an external agent with a `write` Bearer
      token can (1) open an HTTP MCP session and call `send_message`,
      (2) receive a `message_created` webhook, verify the
      `X-AloStudio-Signature: sha256=<hex>` header, dedupe by
      `event_id`, filter outgoing, and reply; (3) call
      `set_ai_mode(conv, on=true)` and watch automation rules stop
      firing on that conversation.

When both pass, v2 closes and the dashboard is ready for the Claude
4.8 backend + frontend audit.

---

## Estimated cadence

**9 sub-milestones, none combined.** Each backend session ends with
the domain test-covered and merged to `main` so the next frontend (or
next backend) session has a clean target.

Order:

1. ✅ `fe.14a` — Contacts list/search/create/detail
2. ✅ `fe.14b` — Contact merge + inline panel
3. ✅ `be.agents` — agents admin (invite + role + remove)
4. ✅ `fe.14c` — Settings → Agents + Profile + Security
5. ⏳ `be.notifications` — Notification model + router + listener
6. ⏳ `fe.14d` — Notification bell + inbox + prefs
7. ⏳ `be.ai-integration-prep` — MCP HTTP transport + webhook polish
8. ⏳ `be.ai-mode` — ai_mode column + tools + automation suppression
9. ⏳ `be.webhook-retries` — ARQ-backed retries with exponential
   backoff and dead-letter visibility

Items 7–9 are the AI-agent integration tail. They land after the
notifications surface because (a) the MCP + webhook plumbing already
works for the common case — these are sharper-edge improvements
surfaced by an external agent (Alicia) trying to consume it; and
(b) the notification inbox is what an *operator* uses while testing
the AI integration, so it makes sense to ship that first.
