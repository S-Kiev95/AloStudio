# F.13 — Chatwoot UI parity review

**Scope:** functional / behavioural parity with Chatwoot OSS v4.13.0, **not**
pixel-for-pixel. We're a React + own design-system port; the goal is that
every feature a Chatwoot OSS user expects exists in some form (or has an
explicit reason it doesn't).

**Methodology:** walked `reference/chatwoot/app/javascript/dashboard/routes/`
+ `reference/chatwoot/app/controllers/api/v1/accounts/` and cross-checked
each surface against the frontend in `frontend/app/`. Reviewed live with
the demo account from `scripts/seed_demo_account.py` against the running
stack (see [frontend/README.md](frontend/README.md) for setup).

**Status legend:**

| Tag | Meaning |
|---|---|
| ✅ | Functional parity — a Chatwoot user finds the feature where they expect it. |
| ⚠️ | Partial — works for the common case but Chatwoot has more depth (filters, bulk actions, edge cases). |
| ⏸ | Deferred — explicit decision documented elsewhere (v2 backlog). |
| ❌ | Missing — should have but doesn't. None in this audit; the gaps are all in ⚠️ or ⏸. |
| 🚀 | Net-new on our side (no Chatwoot equivalent). |

---

## 1. Top-level navigation

Chatwoot upstream nav (left rail icons):

- Conversations · Contacts · Reports · Campaigns · Help Center · Captain
  (AI) · Notifications · Settings.

Our nav (`frontend/components/shell/nav.ts`):

- Inicio · Conversaciones · Instagram 🚀 · Productos 🚀 · Help Center · Campañas · Reportes · Ajustes.

**Differences:**

* We surface **Instagram** as a top-level item because the channel has its
  own publishing + comments tooling (not just message routing like Chatwoot).
* We add a **Productos** catalogue at the top level (own extension, links
  into IG posts).
* We omit **Contacts** (⏸ deferred to v2).
* We omit **Captain / Notifications** as top-level items (⏸; below).
* "Inicio" is our account home placeholder — Chatwoot defaults straight into
  conversations.

---

## 2. Conversations

| Feature | Chatwoot | Us | Notes |
|---|:---:|:---:|---|
| Inbox list | ✅ | ✅ | `frontend/components/conversations/conversation-list.tsx` — list with status/priority/labels filters, unread badges. |
| Conversation detail thread | ✅ | ✅ | `conversation-view.tsx` — messages, send reply, internal note toggle. |
| Realtime updates | ✅ | ✅ | `useCable` invalidates the query keys on cable events. |
| Assignee / team / labels actions | ✅ | ✅ | `conversation-actions.tsx` — assign agent, assign team, toggle labels, set priority. |
| Status toggle (open / resolved / pending / snoozed) | ✅ | ✅ | `useToggleStatus`. |
| Bulk actions (assign N convos, etc.) | ✅ | ⚠️ | We expose per-conversation actions; no bulk-select UI. (Chatwoot's `BulkActionsController`.) |
| Custom filters / saved views | ✅ | ⚠️ | We have status/priority filters but no save-view feature. Chatwoot's `customviews/`. |
| Inline customer details panel | ✅ | ⚠️ | The detail page focuses on the thread; Chatwoot has a right-hand contact panel. Lands with Contacts (F.4 / v2). |
| Macros applied from conversation | ✅ | ⚠️ | Backend has `POST /macros/:id/execute`; frontend doesn't expose the "Run macro on this conversation" UI yet. **Quick win.** |
| Conversation participants (additional agents) | ✅ | ❌ | `ConversationParticipant.vue` upstream; not exposed. ⏸ to follow-up. |
| Search across messages | ✅ | ❌ | `SearchController`; not in our UI. ⏸. |

**Verdict:** core flow (read + reply + label + assign + resolve) is parity.
The gaps are power-user features (bulk, search, saved views).

---

## 3. Contacts ✅

Landed in v2.1 (`fe.14a`) + v2.2 (`fe.14b`).

| Surface | Chatwoot | Us | Notes |
|---|:---:|:---:|---|
| List + search + pagination | ✅ | ✅ | `/accounts/{id}/contacts` — search by name/email/phone/identifier, 15/page. |
| Create + edit + delete | ✅ | ✅ | Form supports name/email/phone/identifier + blocked toggle + custom attributes. |
| Detail view | ✅ | ✅ | Conversations list, notes, custom-attribute editor, contactable-inboxes panel. |
| Merge | ✅ | ✅ | Pick "merge target" dialog from the detail header. |
| Inline panel in conversation | ✅ | ✅ | Right-hand panel in conversation detail (fe.14b). |
| Segments + companies | ✅ | ❌ | Power-user features; ⏸ for now. |

---

## 4. Reports

| Surface | Chatwoot | Us | Notes |
|---|:---:|:---:|---|
| Overview cards | ✅ | ✅ | `frontend/components/reports/reports-view.tsx` — 4 live counters + 7 summary cards with vs-previous delta. |
| Conversations report (timeseries) | ✅ | ✅ | Daily-bucketed bar chart, metric selector (7/30/90 d range). |
| CSAT report | ✅ | ✅ | Under Ajustes → CSAT (`settings/csat`). Includes metrics + per-rating distribution + response list with feedback. |
| Agent / Team / Inbox / Label reports | ✅ | ⚠️ | Backend has `/summary_reports/{agent,team,inbox,label}`; we expose the global summary but no per-entity drill-down UI. **Mediano follow-up.** |
| Bot / SLA / Conversation-traffic | ✅ | ❌ | Chatwoot has these; backend skipped them in Phase 7. ⏸ until backend ports. |
| CSV export | ✅ | ❌ | `csat_survey_responses_controller#download` exists on the backend (deferred). ⏸. |

**Verdict:** the dashboard's main "what's happening" surface is covered.
The per-entity drill-downs are the obvious gap.

---

## 5. Help Center

| Feature | Chatwoot | Us | Notes |
|---|:---:|:---:|---|
| Portals CRUD (admin) | ✅ | ✅ | `frontend/components/help-center/portal-form.tsx`. |
| Categories CRUD per portal | ✅ | ✅ | `categories-panel.tsx` (within portal detail). |
| Articles CRUD with status (draft/published/archived) | ✅ | ✅ | `article-form.tsx`, filter chips, status badges. |
| Article author + views meta | ✅ | ✅ | View count rendered; author_id comes from the backend. |
| Locale switcher per portal | ✅ | ⚠️ | Locale is editable per article/category; we don't surface a portal-level locale picker like Chatwoot's. **Quick win.** |
| Public Help Center site | ✅ | ✅ 🚀 | We ship our own SSG/ISR version (`/hc/<slug>` with `revalidate=300`), with `react-markdown` + remark-gfm + `robots.txt`. Chatwoot's is a Rails-rendered HTML view; ours is more SEO-friendly. |
| Public search | ✅ | ❌ | Chatwoot has client-side article search on the public site. ⏸. |
| Article embeddings (pgvector) | ✅ enterprise | ❌ | Backend `portals/router.py` notes this is Phase 10 deferred. ⏸. |
| Logo upload | ✅ | ❌ | Backend defers ActiveStorage uploads to Phase 10. ⏸. |

**Verdict:** admin CRUD + public site = parity. Public search is the
most-missed gap; logo upload is blocked on backend ActiveStorage.

---

## 6. Campaigns

| Feature | Chatwoot | Us | Notes |
|---|:---:|:---:|---|
| Ongoing campaigns (widget trigger) | ✅ | ✅ | `campaign-form.tsx` — URL pattern + time-on-page + business-hours-only. |
| One-off campaigns (scheduled blasts) | ✅ | ✅ | `scheduled_at` datetime + audience label multi-select. |
| Enable / disable toggle | ✅ | ✅ | In the form; the list shows the badge. |
| Sender + inbox pickers | ✅ | ✅ | Reuses `useAgents` + `useInboxes`. |
| Template params (WhatsApp, etc.) | ✅ | ⚠️ | Backend has `template_params`; frontend form doesn't expose it (no WhatsApp inbox to use it on). ⏸ until WhatsApp inbox lands. |
| Campaign analytics / delivery stats | ✅ | ❌ | Chatwoot shows sent/clicked counts per campaign; no equivalent on our side. The scheduler runtime is deferred (backend Phase 10). ⏸. |

**Verdict:** CRUD + audience definition = parity. The runtime stats land
when the backend ports the campaign scheduler.

---

## 7. Settings

12 sub-sections — Chatwoot has more (15+ on enterprise). Here's the map:

| Sub-section | Chatwoot | Us | File / Notes |
|---|:---:|:---:|---|
| Account / Profile / Security | ✅ | ✅ | `settings/profile` (name/email/phone/signature) + `settings/security` (password change). Landed in fe.14c. |
| Agents (invite + role management) | ✅ | ✅ | `settings/agents` — invite form, role promote/demote, remove. Backend `be.agents` ships the mailer + invitation link. Landed in v2.3 + v2.4. |
| Teams ✅ | ✅ | ✅ | `settings/teams` with members panel. |
| Inboxes (channel CRUD) | ✅ | ⚠️ | We list inboxes via `useInboxes` for pickers and the Instagram flow shows IG-channel detail; we don't surface a generic per-channel CRUD page. Chatwoot has wizards for 10+ channels. **Tier 1 of v2.** |
| Labels ✅ | ✅ | ✅ | `settings/labels`. |
| Macros ✅ | ✅ | ✅ | `settings/macros` with the actions editor. |
| Canned responses | ✅ | ⏸ | Backend not ported (sidebar shows it as pending with milestone "F.9C"). |
| Automation rules ✅ | ✅ | ✅ | `settings/automation` with the conditions + actions editor, clone, active-toggle. |
| Webhooks ✅ | ✅ | ✅ | `settings/webhooks` with subscription chips. |
| Agent bots ✅ | ✅ | ✅ | `settings/agent_bots` with the reveal-once secret pattern. |
| Integrations ✅ | ✅ | ⚠️ | `settings/integrations` lists the app catalogue + can delete hooks. The "Connect" flow per provider (OAuth dance) is explicitly noted as future work in the UI. |
| Custom attributes ✅ | ✅ | ✅ | `settings/custom_attributes` with list-type values + regex. |
| Working hours ✅ | ✅ | ✅ | `settings/working_hours` with the bulk 7-day editor. |
| CSAT ✅ | ✅ | ✅ | `settings/csat` — see Reports section. |
| Assignment policy / SLA | ✅ | ❌ | Backend not ported (Chatwoot's `AssignmentPolicy` + `SLA`). ⏸. |
| Audit logs | ✅ enterprise | ❌ | Not ported. ⏸. |
| Custom roles | ✅ enterprise | ❌ | Enterprise feature. ⏸. |
| Captain settings | ✅ | ❌ | AI assistant — newer Chatwoot feature. ⏸. |
| Billing | ✅ | ❌ | SaaS-specific. ⏸ (not relevant for self-hosted). |

**MCP Tokens 🚀** (`settings/mcp_tokens`) — net-new on our side. Admin
CRUD over the Bearer tokens the MCP server uses to authenticate AI
agents. Mirrors GitHub-PAT UX (secret revealed once).

---

## 8. Notifications ✅

Landed in v2.5 (`be.notifications`) + v2.6 (`fe.14d`).

| Surface | Chatwoot | Us | Notes |
|---|:---:|:---:|---|
| Backend model + listener | ✅ | ✅ | `Notification` polymorphic actor + `NotificationSetting` (JSONB arrays instead of bit-packed ints). Listener fires on `conversation.created`, `assignee.changed`, `message.created`. |
| Realtime cable broadcast | ✅ | ✅ | `notification.created` event published to the user's pubsub_token channel → bell updates without polling. |
| Topbar bell + badge + dropdown | ✅ | ✅ | `components/shell/notification-bell.tsx` — unread count poll + live invalidation. Mark-read / delete / mark-all-read actions. |
| Full inbox page | ✅ | ✅ | `/accounts/{id}/notifications` — paginated with all/unread filter tabs. |
| Per-user preferences | ✅ | ⚠️ | `settings/notifications` — checkbox matrix (5 types × email/push). The preferences **persist** but are **not yet enforced**: the in-app row is always created (correct, matches Chatwoot), and the email/push delivery these flags gate is deferred (`listener.py` docstring). So toggling has no runtime effect today — it's wired for when the email/push worker lands. |

---

## 9. Captain (AI) ⏸

Newer Chatwoot feature (assistants, documents, responses, tools).
Out of scope for v1 — overlaps conceptually with our MCP server
extension. ⏸ unless we decide to converge on Chatwoot's surface.

---

## 10. Our extensions on top 🚀

Things we ship that Chatwoot OSS doesn't:

* **Instagram publishing** (`/instagram/posts`) — full media-type
  composer (IMAGE / VIDEO / REELS / CAROUSEL / STORIES), schedule
  for later, product tagging, container status polling, comments
  moderation (reply / hide / delete) per post. Chatwoot only treats
  Instagram as a DM inbox.
* **Products catalogue** (`/products`) — CRUD for product entries,
  linked into IG posts as `product_ids` in the create-post payload.
* **MCP Tokens** (`settings/mcp_tokens`) — admin surface for tokens
  consumed by the MCP server (FastMCP) that AI agents use to call
  AloStudio tools. Scope-aware (read/write/admin), rotate + reveal-once.
* **Public Help Center as Next.js ISR** — same `/hc/<slug>` URL space
  as Chatwoot but server-rendered with `revalidate=300`, ~176 B client
  JS per article, robots.txt allow-list. Chatwoot ships Rails HTML.

---

## 11. Architectural differences worth flagging

These aren't gaps — they're explicit divergences from Chatwoot.

* **BFF cookie ↔ devise header bridge.** Chatwoot stores the auth token
  in `localStorage` (XSS-readable). We store it in httpOnly cookies
  and bridge to devise headers in the BFF route. Strictly better.
* **TanStack Query instead of Vuex.** Cache invalidation is explicit
  via `queryClient.invalidateQueries` rather than store mutations.
  Cable events drive cache invalidations rather than store hydration.
* **Tailwind + own design system tokens.** Chatwoot uses Bulma + custom
  CSS. Our `:root` / `.dark` token set is more constrained — fewer
  one-off colour values, more predictable theming.
* **Server components for the public Help Center.** Public articles
  ship ~176 B client JS. Lighthouse should be ≥ 95 on a clean device.
* **Conversations realtime over native WebSocket.** Chatwoot uses
  ActionCable's JavaScript client; we hand-rolled a tiny ActionCable
  protocol implementation (`lib/realtime/cable.ts`). Lighter weight,
  ~3 kB.

---

## 12. Quick-win backlog

Concrete follow-ups, ordered by effort:

1. **Run-macro-on-conversation button.** Add a "Macros" dropdown to
   `conversation-actions.tsx` that lists global+personal macros, calls
   `POST /macros/:id/execute` with `{conversation_ids: [displayId]}`.
   Backend + hook (`useExecuteMacro`) already exist. ~30 min.
2. **Portal locale picker.** Add a locale select to the portal-level
   admin header so categories/articles list filtered by locale.
   Backend supports `?locale=`. ~45 min.
3. **Profile / security pages.** Add a client-side profile hook (today
   `lib/auth/profile.ts:getProfile` is server-only), wire it into
   `/settings/profile` and `/settings/security`. Devise has the routes
   (`/auth/password`, profile update via `/api/v1/profile`). ~3 h.
4. **Notification bell.** Top-right of the dashboard shell. Backend has
   `/notifications`. ~3-4 h (component + popover + mark-read).
5. **Agent invitations.** Settings → Agents page with the invite form.
   Backend has the controller. ~3-4 h.
6. **Inbox CRUD (generic).** Per-channel forms (Email / API / Website
   widget). The backend wires several channel types. Big — ~1-2 days.
7. **Bulk-actions toolbar in conversations.** Selectable rows + bulk
   assign / label / status. ~1 day.
8. **Custom filters / saved views.** Power-user feature; sizeable.
   ~2-3 days.
9. **Per-entity reports drill-downs** (`/reports/agents`,
   `/reports/teams`, etc.). Backend endpoints exist. ~1-2 days.
10. **Public Help Center search.** Algolia-style or Postgres FTS.
    ~1-2 days.

Items 1-3 could land as a single `fe.14` polish commit if we want a
v1.1 closer.

---

## 13. Explicit out-of-scope (v1, now mostly closed in v2)

* ~~**Contacts domain** — deferred to v2.~~ ✅ Shipped in v2.1 / v2.2.
* ~~**Notifications inbox** — runtime infra ready, UI gap.~~ ✅ Shipped in v2.5 / v2.6.
* ~~**Agent invitations + profile / security pages.**~~ ✅ Shipped in v2.3 / v2.4.
* **SaaS billing** — not relevant for self-hosted.
* **Enterprise tiers** (audit logs, custom roles, SSO sometimes) —
  defer indefinitely; revisit when there's a customer.
* **Captain AI** — conceptual overlap with MCP; defer.
* **SLA / Assignment policy** — backend not ported.
* **Article embeddings (pgvector)** — backend Phase 10.
* **File uploads on articles / agent avatars** — ActiveStorage
  equivalent not ported (MinIO is in Docker but not wired).

---

## Verdict

**The dashboard is at functional parity with Chatwoot OSS for the
common workflows** an agent or admin uses day to day — conversations
(read/reply/route), settings (all the admin CRUD that lets the
account work), reports overview, campaigns, help-center authoring.

The honest gaps **after v2 closeout** are:

* ~~No Contacts surface~~ — closed in v2.1/v2.2.
* ~~No notification inbox~~ — closed in v2.5/v2.6.
* ~~No agent invitations / profile editing~~ — closed in v2.3/v2.4.
* **AI-agent integration polish (v2.7–v2.9)** — closed: HTTP MCP
  transport, dual signature header, `event_id` in body, `sender_type`,
  `Conversation.ai_mode` + tools + automation suppression, ARQ-backed
  webhook retries with exponential backoff + dead-letter visibility.
* **Power-user features** (bulk actions, saved views, full search) —
  small per-item, several items. **Remaining ⏸.**

**Net result:** an end user moving from Chatwoot would find every
common feature where they expect it; the gaps are at the depth /
power-user end, not at the surface level.
