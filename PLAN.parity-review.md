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
| ❌ | Missing — the few left are backend-blocked report/policy types (see §12). |
| 🚀 | Net-new on our side (no Chatwoot equivalent). |

---

> **Refreshed 2026-07-03** — a feature batch closed most of the ⚠️/❌ gaps
> the original audit found. Shipped since the v2 closeout: full inbox
> onboarding UI (list + add wizard + detail + channel picker), conversation
> full-text search, bulk actions (status/assign/labels), advanced filter
> builder + saved views, run-macro-on-conversation, conversation
> participants, per-entity report drill-downs, report CSV + Excel export,
> one-off + ongoing campaign delivery + per-campaign analytics, notification
> email worker, attachment uploads (dashboard composer + public widget),
> Help Center portal locale picker + article search, canned responses,
> contact companies, and the integrations Connect flow. Rows below are
> updated in place; the quick-win backlog (§12) is largely cleared and the
> genuinely-remaining gaps are consolidated in §12 + §13.

> **Refreshed 2026-07-13** — AloStudio now runs on a public staging VPS
> (Tailscale Funnel) wired live to Meta. WhatsApp Cloud is connected end
> to end (inbound text/image/audio/location, outbound text/template/media,
> dashboard-only soft-delete + composer image preview). Instagram **DMs
> work end-to-end (inbound + outbound)** via the **Facebook-Page** Graph
> API flow — connected with the manual-token form (`login_type=facebook`,
> canonical IG Business Account id + a Page access token), Page subscribed
> to the app's `messages` webhook. The newer **Instagram-Login** API was
> tried first but delivered only content-less `message_edit` webhooks in
> the dev/tester setup, so it was abandoned. Dev-mode caps replies to
> accounts with an app role; messaging arbitrary customers needs App
> Review (Advanced Access on `instagram_business_manage_messages`). No app
> code changed — the existing `process_instagram_webhook` +
> `send_text_message_instagram` handled both directions. See memory
> `project-instagram-dm-integration`.

> **Refreshed 2026-07-17** — Instagram DM **media works both ways** on
> staging. Inbound (`app/domains/instagram/media.py` +
> `_build_ig_attachments`) fetches the signed CDN URL Meta puts straight in
> the webhook — one GET, no `media_id` hop like WhatsApp — and attaches
> image / audio / video / file / share / story_mention / ig_reel / ig_post /
> ig_story; a shape we don't handle now logs
> `instagram.inbound.unhandled_attachment` instead of minting an empty
> bubble. Outbound sends `payload.url` at a signed, expiring
> `/public/attachments/{id}` route Meta pulls — IG rejects Messenger's
> reusable `attachment_id` — and commits the row before handing the link
> over so Meta's fetch can't race the create-message transaction. Verified
> live end-to-end (image, voice note, shared post in; image out). Still
> open: Instagram **posts/publishing** wants a live exercise, and
> messaging any non-tester still needs App Review.

---

## 1. Top-level navigation

Chatwoot upstream nav (left rail icons):

- Conversations · Contacts · Reports · Campaigns · Help Center · Captain
  (AI) · Notifications · Settings.

Our nav (`frontend/components/shell/nav.ts`):

- Inicio · Conversaciones · Contactos · Instagram 🚀 · Productos 🚀 · Help Center · Campañas · Reportes · Ajustes.

**Differences:**

* We surface **Instagram** as a top-level item because the channel has its
  own publishing + comments tooling (not just message routing like Chatwoot).
* We add a **Productos** catalogue at the top level (own extension, links
  into IG posts).
* **Contacts** is a top-level item (shipped in v2.1/v2.2).
* **Notifications** is a topbar bell rather than a left-rail item; **Captain**
  is out of scope (⏸; below).
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
| Bulk actions (assign N convos, etc.) | ✅ | ✅ | Multi-select toolbar → bulk status / assign-agent / add+remove labels over `BulkActionsController`. |
| Custom filters / saved views | ✅ | ✅ | Advanced filter builder UI + saved views (`custom_filters`); the list's "save this filter" affordance. |
| Inline customer details panel | ✅ | ✅ | Right-hand `contact-panel.tsx` in the conversation detail (fe.14b). |
| Macros applied from conversation | ✅ | ✅ | "Correr macro…" dropdown in `conversation-actions.tsx` → `POST /macros/:id/execute`. |
| Conversation participants (additional agents) | ✅ | ✅ | `conversation-participants.tsx` — watcher chips + add picker (inbox-access enforced backend-side). |
| Search across messages | ✅ | ✅ | Full-text (ILIKE) message search in the conversation list, permission-scoped. |
| Attachment uploads in composer | ✅ | ✅ 🚀 | Multi-file picker → pre-signed direct upload (SigV4) → message attachments; also enabled on the public widget. |

**Verdict:** full parity for the day-to-day flow **and** the power-user
surface — read/reply/route, bulk actions, search, saved views, macros,
participants. No remaining ⚠️ in this section.

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
| Companies | ✅ | ✅ | Roll-up over `additional_attributes.company_name` (`GET /contacts/companies`) + company chips that filter the list via `?company=`. Chatwoot ships no Company model either — same derived approach. |
| Segments (saved contact filters) | ✅ | ✅ | `POST /contacts/filter` (contact filter DSL over name/email/phone/identifier/company_name/blocked/created_at) + a "Filtros" builder and saved segment chips backed by `CustomView(filter_type: contact)`. |

---

## 4. Reports

| Surface | Chatwoot | Us | Notes |
|---|:---:|:---:|---|
| Overview cards | ✅ | ✅ | `frontend/components/reports/reports-view.tsx` — 4 live counters + 7 summary cards with vs-previous delta. |
| Conversations report (timeseries) | ✅ | ✅ | Daily-bucketed bar chart, metric selector (7/30/90 d range). |
| CSAT report | ✅ | ✅ | Under Ajustes → CSAT (`settings/csat`). Includes metrics + per-rating distribution + response list with feedback. |
| Agent / Team / Inbox / Label reports | ✅ | ✅ | Per-entity drill-down tables under the "Desglose" scope switcher. |
| Report export (CSV) | ✅ | ✅ | Per-entity summary download (`/summary_reports/{scope}/export?format=csv`), UTF-8 BOM for Excel. |
| Report export (Excel .xlsx) | ✅ | ✅ 🚀 | Same endpoint, `format=xlsx` — a dependency-free hand-rolled single-sheet workbook. Chatwoot only offers CSV. |
| Conversation-traffic heatmap | ✅ | ✅ | `GET /reports/conversation_traffic` — conversations by (local date × hour-of-day), rendered as a heatmap. Derived from `conversations.created_at`. |
| Bot report | ✅ | ✅ | `GET /reports/bot_metrics` — conversation/message counts + resolution & handoff rates over the range, in a "Rendimiento del bot" section on the reports page. Backed by new bot-handling tracking: the reporting listener now writes `conversation_bot_resolved` (bot resolved with no human reply) + `conversation_bot_handoff` (deduped). |
| SLA report | ✅ enterprise | ❌ | SLA is enterprise-only (`enterprise/`). ⏸. |

**Verdict:** overview + per-entity drill-downs + CSV/Excel export + the
conversation-traffic heatmap + the bot report = parity (export exceeds it).
Only the SLA report remains, and it's an enterprise feature.

---

## 5. Help Center

| Feature | Chatwoot | Us | Notes |
|---|:---:|:---:|---|
| Portals CRUD (admin) | ✅ | ✅ | `frontend/components/help-center/portal-form.tsx`. |
| Categories CRUD per portal | ✅ | ✅ | `categories-panel.tsx` (within portal detail). |
| Articles CRUD with status (draft/published/archived) | ✅ | ✅ | `article-form.tsx`, filter chips, status badges. |
| Article author + views meta | ✅ | ✅ | View count rendered; author_id comes from the backend. |
| Locale switcher per portal | ✅ | ✅ | Portal-level locale `<select>` (from `config.allowed_locales`) filtering the article + category panels. |
| Public Help Center site | ✅ | ✅ 🚀 | We ship our own SSG/ISR version (`/hc/<slug>` with `revalidate=300`), with `react-markdown` + remark-gfm + `robots.txt`. Chatwoot's is a Rails-rendered HTML view; ours is more SEO-friendly. |
| Article search (dashboard + public) | ✅ | ✅ | ILIKE search over title/description/content — a debounced box in the dashboard `ArticlesPanel` and `?query=` on the public `/hc/<slug>/articles` endpoint. |
| Article embeddings (pgvector) | ✅ enterprise | ✅ | Captain-style semantic search: on save an article is expanded into search terms (`gpt-4o`), each term embedded (`text-embedding-3-small`) into a `vector(1536)` on `article_embeddings`, indexed off the request via ARQ. Public `?query=` embeds the query and does cosine nearest-neighbour (hnsw index), falling back to ILIKE when the key is unset or OpenAI errors. Gated on `OPENAI_API_KEY`. |
| Logo upload | ✅ | ✅ | `portals.logo` + a Logo field in the portal form (uploads via the MinIO pipeline); the detail header shows it. |

**Verdict:** admin CRUD + public site + locale picker + article search +
logo upload + semantic embedding search = **full parity** (embeddings are an
enterprise feature in Chatwoot). A net-new admin **"Reindexar búsqueda"**
action (`POST /portals/{slug}/reindex`) backfills a portal whose articles
predate the key — beyond what Chatwoot offers (it only re-embeds on save).

---

## 6. Campaigns

| Feature | Chatwoot | Us | Notes |
|---|:---:|:---:|---|
| Ongoing campaigns (widget trigger) | ✅ | ✅ | `campaign-form.tsx` — URL pattern + time-on-page + business-hours-only. |
| One-off campaigns (scheduled blasts) | ✅ | ✅ | `scheduled_at` datetime + audience label multi-select. |
| Enable / disable toggle | ✅ | ✅ | In the form; the list shows the badge. |
| Sender + inbox pickers | ✅ | ✅ | Reuses `useAgents` + `useInboxes`. |
| One-off delivery runtime | ✅ | ✅ | The ARQ scheduler builds a conversation + outgoing message per audience contact (`CampaignConversationBuilder`). |
| Ongoing trigger runtime | ✅ | ✅ | Widget `campaign.triggered` event → `CampaignListener` fires the ongoing campaign for a visitor. |
| Campaign analytics / delivery stats | ✅ | ✅ 🚀 | `GET /campaigns/:id/analytics` → conversations created + a sent/delivered/read/failed breakdown, surfaced as an "Entrega" panel on the campaign detail. Chatwoot's is thinner. |
| Template params (WhatsApp, etc.) | ✅ | ✅ | When the picked inbox is WhatsApp the form swaps the free-text message for an approved-template picker: `GET .../inboxes/:id/whatsapp/templates` lists them (with a "Sincronizar" button → `POST .../sync` refreshing from Meta), the body preview substitutes each `{{n}}`, and per-variable inputs build `template_params`. Verified live: the `TestWhatsapp` inbox synced `hello_world` from the real WABA. |

**Verdict:** CRUD + audience + one-off/ongoing delivery runtime + per-campaign
analytics + WhatsApp template params = **full parity** (analytics exceeds it).

---

## 7. Settings

12 sub-sections — Chatwoot has more (15+ on enterprise). Here's the map:

| Sub-section | Chatwoot | Us | File / Notes |
|---|:---:|:---:|---|
| Account / Profile / Security | ✅ | ✅ | `settings/profile` (name/email/phone/signature) + `settings/security` (password change). Landed in fe.14c. |
| Agents (invite + role management) | ✅ | ✅ | `settings/agents` — invite form, role promote/demote, remove. Backend `be.agents` ships the mailer + invitation link. Landed in v2.3 + v2.4. |
| Teams ✅ | ✅ | ✅ | `settings/teams` with members panel. |
| Inboxes (channel CRUD) | ✅ | ✅ | `settings/inboxes` — list + add wizard (channel picker incl. FB/IG), per-inbox detail/settings page with agent assignment + webhook URL / verify token surfaced. |
| Labels ✅ | ✅ | ✅ | `settings/labels`. |
| Macros ✅ | ✅ | ✅ | `settings/macros` with the actions editor. |
| Canned responses | ✅ | ✅ | `settings/canned_responses` — CRUD + `?search=` ranking; composer `/short_code` quick-insert picker. |
| Automation rules ✅ | ✅ | ✅ | `settings/automation` with the conditions + actions editor, clone, active-toggle. |
| Webhooks ✅ | ✅ | ✅ | `settings/webhooks` with subscription chips. |
| Agent bots ✅ | ✅ | ✅ | `settings/agent_bots` with the reveal-once secret pattern. |
| Integrations | ✅ | ⚠️ | `settings/integrations` — app catalogue + hook CRUD + a **Connect** affordance: OAuth link for external apps (Slack/Linear, resolved from `slack_client_id`/`linear_client_id`) and an inline settings form for API-key apps (openai/dialogflow/webhook/dyte). The OAuth **callback** (code→token exchange) is the per-vendor follow-up — needs real provider credentials. |
| Custom attributes ✅ | ✅ | ✅ | `settings/custom_attributes` with list-type values + regex. |
| Working hours ✅ | ✅ | ✅ | `settings/working_hours` with the bulk 7-day editor. |
| CSAT ✅ | ✅ | ✅ | `settings/csat` — see Reports section. |
| Assignment policy | ✅ | ✅ | `settings/assignment_policies` — admin-only CRUD (round-robin order, `earliest_created`/`longest_waiting` priority, fair-distribution limit/window, enabled) + the singular per-inbox link (one policy per inbox). Runtime enforcement of the fair-distribution cap in the auto-assignment path is a follow-up stage. |
| SLA | ✅ enterprise | ❌ | Enterprise (`enterprise/app/models`). ⏸. |
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
| Email delivery worker | ✅ | ✅ | ARQ task sends the notification email (aiosmtplib → MailHog in dev), gated on the user's email preference. |
| Web-push delivery worker | ✅ | ✅ | Hand-rolled RFC 8291 / VAPID crypto (`app/core/webpush.py`, verified vs the RFC test vector) + a `NotificationSubscription` model + an ARQ send task + a service-worker toggle. Needs `VAPID_*` env keys configured (else it no-ops). |
| Per-user preferences | ✅ | ✅ | `settings/notifications` — checkbox matrix (5 types × email/push); both columns are now enforced by their delivery workers. |

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

## 12. Backlog

**The original 10 quick-wins are all shipped** (run-macro-on-conversation,
portal locale picker, profile/security pages, notification bell, agent
invitations, generic inbox CRUD, bulk-actions toolbar, saved views,
per-entity report drill-downs, public Help Center search). **Contacts
segments**, **agent avatars**, **portal logos**, **web-push delivery**,
the **conversation-traffic heatmap**, and **assignment policies** shipped
too — the "shippable now" bucket is now empty; every remaining item is
gated on an external credential or a backend port.

**Blocked on external credentials:**

1. **Integrations OAuth callback.** Per-vendor `code → token` exchange +
   hook creation (Slack, Linear, Shopify). The Connect *start* is wired;
   the return leg needs registered provider apps + secrets. Per vendor.

(Shipped recently: **WhatsApp campaign `template_params`** — the campaign
form's template picker + `/whatsapp/templates` sync endpoint, verified live
against the `TestWhatsapp` WABA (`hello_world` synced); article embeddings
(pgvector) — Captain-style semantic
Help-Center search, needs `OPENAI_API_KEY`; the bot report —
`GET /reports/bot_metrics` + bot-handling tracking (`conversation_bot_resolved`
/ `conversation_bot_handoff` events); assignment policies — OSS
`AssignmentPolicy` CRUD + per-inbox link, admin-only; web-push delivery —
RFC 8291 + VAPID, needs ``VAPID_*`` keys; conversation-traffic heatmap. Only
the **SLA** report type remains and it's enterprise-only, deferred with the
other enterprise tiers.)

---

## 13. Explicit out-of-scope (v1, now mostly closed in v2)

* ~~**Contacts domain** — deferred to v2.~~ ✅ Shipped in v2.1 / v2.2.
* ~~**Notifications inbox** — runtime infra ready, UI gap.~~ ✅ Shipped in v2.5 / v2.6.
* ~~**Agent invitations + profile / security pages.**~~ ✅ Shipped in v2.3 / v2.4.
* **SaaS billing** — not relevant for self-hosted.
* **Enterprise tiers** (audit logs, custom roles, SSO sometimes) —
  defer indefinitely; revisit when there's a customer.
* **Captain AI** — conceptual overlap with MCP; defer.
* ~~**Assignment policy**~~ ✅ Shipped — OSS `AssignmentPolicy` CRUD +
  per-inbox link. **SLA** stays deferred (enterprise-only).
* ~~**Article embeddings (pgvector)**~~ ✅ Shipped — Captain-style semantic
  Help-Center search (`OPENAI_API_KEY`-gated), even though it's an
  enterprise feature in Chatwoot.
* ~~**File uploads (attachments / agent avatars / portal logos)**~~ — the
  MinIO SigV4 pipeline is wired for message + widget attachments, agent
  avatars, and portal logos. **Done.**

---

## Verdict

**The dashboard is at functional parity with Chatwoot OSS for the
common workflows** an agent or admin uses day to day — conversations
(read/reply/route), settings (all the admin CRUD that lets the
account work), reports overview, campaigns, help-center authoring.

The honest gaps **after the 2026-07-03 batch** are:

* ~~No Contacts surface~~ — closed in v2.1/v2.2 (+ companies, this batch).
* ~~No notification inbox~~ — closed in v2.5/v2.6 (+ email worker, this batch).
* ~~No agent invitations / profile editing~~ — closed in v2.3/v2.4.
* ~~Power-user conversation features~~ (bulk actions, saved views, full
  search, macros-on-conversation, participants) — **all closed this batch.**
* ~~Inbox onboarding, report drill-downs + export, campaign delivery +
  analytics, Help Center locale + search, canned responses~~ — **closed
  this batch.**

What's left is now **entirely dependency-gated** (see §12): the "shippable
now" bucket is empty. The integrations OAuth callback needs provider
credentials — the last of the ⚠️s. (WhatsApp `template_params` and article
embeddings both shipped this batch once the WABA token / `OPENAI_API_KEY`
were provided.) The indefinitely-deferred set (Captain AI, enterprise
audit/roles/SSO, SaaS billing) is unchanged — except semantic Help-Center
search, which we ported despite its enterprise origins.

**Net result:** an end user moving from Chatwoot finds every common **and**
most power-user features where they expect them; the remaining gaps are at
the enterprise / external-credential / not-yet-ported-backend edge.
