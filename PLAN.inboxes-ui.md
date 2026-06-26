# PLAN — Inboxes / Channels onboarding UI (Bandejas de entrada)

**Goal:** add the "add a messaging channel" surface that Chatwoot has under
Settings → Inboxes but that AloStudio's frontend never built. Today only
Instagram has a connect UI (top-level nav); WhatsApp / Telegram / SMS / Email /
Website widget / API have **no UI** to create or manage them.

Status: **scoped, ready to start.** Branch off `main` (e.g. `feat/inboxes-ui`).

---

## Key finding — the backend is ~95% ready

`app/domains/inboxes/` already has the full CRUD router + a builder that
**creates every channel type**:

- `app/domains/inboxes/service.py` → `InboxBuilder._build_channel` has working,
  validated create paths for: `api`, `web_widget`, `email`, `whatsapp`
  (cloud + 360dialog), `facebook`, `instagram`, `twilio_sms`, `sms` (Bandwidth),
  `telegram`. (The module docstring saying "Phase 2: only Channel::Api" is
  **stale** — ignore it; the code at lines ~212-282 dispatches all 9.)
- `app/domains/inboxes/router.py` → `GET/POST/GET:id/PATCH/DELETE /inboxes`
  + `reset_secret` + `inbox_members` GET/POST/PATCH/DELETE. All wired.
- `app/domains/inboxes/models.py` → all channel tables already exist
  (`channel_whatsapp`, `channel_telegram`, `channel_twilio_sms`, `channel_sms`,
  `channel_email`, `channel_web_widgets`, `channel_facebook_pages`,
  `channel_instagram`, `channel_api`). **No migrations needed.**

### The actual backend gap (small)
The HTTP layer only *exposes* the `Channel::Api` fields, so non-Api creates
can't get their params through:
1. `schemas.py` → `ChannelCreate` is `extra="ignore"` with only
   `type/webhook_url/hmac_mandatory/additional_attributes`. Change to
   `extra="allow"` (pydantic v2 keeps extras in `model_dump()`).
2. `router.py` `create_inbox` → replace the hardcoded 3-field `channel_params`
   with `payload.channel.model_dump(exclude={"type"})` so the full per-channel
   dict reaches the builder.
3. `router.py` `_load_channel` / `destroy_inbox` → today they only resolve
   `ApiChannel`; generalize to resolve the right channel table by
   `inbox.channel_type` (otherwise **non-Api delete orphans the channel row**,
   and show/edit can't read channel detail). Add a `channel_model_for(type)` map.
4. `presenters.py` `present_inbox` → surface per-channel detail (phone_number,
   bot_name, provider, etc.) for show. Minimal for v1 (name + channel_type is
   enough for the list).
5. (Optional) per-channel PATCH editable fields (today update only handles
   `Channel::Api::EDITABLE_ATTRS`).
6. Integration tests: create each channel type via HTTP (the builder paths are
   likely service-tested already; add the HTTP-level coverage).

**Backend estimate: ~0.5 day** (item 1-2 are minutes; 3-4 are the real work).

---

## Per-channel field reference (exact, from `InboxBuilder`)

Use this to build the forms. `name` (inbox name) is always required.
`channel.type` is the short key. Required = ⬤, optional = ○.

| Channel | `type` | Fields |
|---|---|---|
| **Telegram** | `telegram` | ⬤ `bot_token` · ○ `bot_name` |
| **WhatsApp (Cloud)** | `whatsapp` (provider=`whatsapp_cloud`) | ⬤ `phone_number` · ⬤ `provider_config.{api_key, phone_number_id, business_account_id}` · (webhook_verify_token auto-generated) |
| **WhatsApp (360dialog)** | `whatsapp` (provider=`default`) | ⬤ `phone_number` · ⬤ `provider_config.{api_key, url}` |
| **SMS — Bandwidth** | `sms` | ⬤ `phone_number` · ⬤ `provider_config.{account_id, api_token, api_secret, application_id}` |
| **SMS/WhatsApp — Twilio** | `twilio_sms` | ⬤ `account_sid` · ⬤ `auth_token` · ⬤ (`phone_number` **or** `messaging_service_sid`) · ○ `api_key_sid` · ○ `medium` (`sms`\|`whatsapp`) |
| **Email** | `email` | ⬤ `email` · ○ IMAP block (if `imap_enabled`: ⬤ `imap_address/imap_port/imap_login` + password/ssl) · ○ SMTP block (if `smtp_enabled`: ⬤ `smtp_address/smtp_port/smtp_login` + password/tls) |
| **Website widget** | `web_widget` | ⬤ `website_url` · ○ `widget_color, welcome_title, welcome_tagline, allowed_domains, pre_chat_form_enabled, continuity_via_email` |
| **API** | `api` | ○ `webhook_url, hmac_mandatory, additional_attributes` |
| **Facebook** | `facebook` | ⬤ `page_id` · ⬤ `page_access_token` · ○ `user_access_token, instagram_id` (real flow is OAuth — manual-token form for now) |
| **Instagram** | `instagram` | ⬤ `instagram_id` · ⬤ `access_token` · ○ `expires_at` (already has its own top-level connect UI — link there instead) |

Shared inbox attributes (step after channel, or in settings): `greeting_enabled/greeting_message`, `enable_auto_assignment`, `csat_survey_enabled`, `working_hours_enabled/out_of_office_message`, `timezone`, `allow_messages_after_resolved`, `lock_to_single_conversation`, `sender_name_type`.

---

## Frontend work (the bulk)

### v1 channel scope (recommended)
Ship the channels our backend supports and that have no other UI:
**Telegram, WhatsApp (Cloud), Bandwidth SMS, Twilio SMS, Website widget, API, Email.**
- **Instagram** → link to the existing top-level Instagram connect flow (don't duplicate).
- **Facebook** → manual-token form (works) or defer to the OAuth flow later.

### API client — extend `frontend/lib/api/inboxes.ts`
Today: only `useInboxes` (GET). Add:
- `useInbox(accountId, id)` (GET one)
- `useCreateInbox(accountId)` → `POST /inboxes` with `{name, channel:{type, ...}, ...inboxAttrs}`
- `useUpdateInbox`, `useDeleteInbox`, `useResetInboxSecret`
- inbox members: `useInboxMembers(inboxId)` (GET `/inbox_members/:id`), `useSetInboxMembers` (PATCH `/inbox_members` body `{inbox_id, user_ids}`)
- reuse the existing agents-list hook (the one campaigns + `conversation-actions` use) for the agent-assignment step.

### Nav
Add **"Bandejas de entrada"** to `frontend/components/settings/settings-sidebar.tsx`
(admin-only item), near the top (Chatwoot puts Inboxes high in settings).

### Routes (`frontend/app/accounts/[accountId]/settings/inboxes/...`)
Mirror Chatwoot's flow (`reference/chatwoot/.../settings/inbox/inbox.routes.js`):
- `inboxes/page.tsx` — **list** (name, channel-type badge, agent count, row → settings; "Agregar canal" CTA).
- `inboxes/new/page.tsx` — **channel-type picker** grid (cards per channel w/ icon).
- `inboxes/new/[channel]/page.tsx` — **per-channel config form** (fields from table above).
- `inboxes/[inboxId]/page.tsx` — **inbox settings** (tabs: General / Agentes / Configuración / Eliminar). General = name + inbox attrs; Agentes = members picker; Config = channel-specific (read-mostly v1); Delete = confirm.
- (Optional) a finish/success step after create showing the webhook URL / verify token to paste into the provider (important for WhatsApp/Telegram).

### Components (`frontend/components/settings/inboxes/`)
- `inboxes-view.tsx` (list, empty/loading/error states, Binance row style).
- `channel-picker.tsx` (grid of channel cards).
- `channel-form-*.tsx` per channel **or** one `channel-form.tsx` driven by a field schema (DRY — recommended given the table above is data).
- `inbox-settings-view.tsx` + `inbox-members-panel.tsx` (reuse the teams members-panel pattern).
- `state` / secret-reveal for webhook verify token (reuse `mcp-tokens/secret-reveal.tsx` pattern).

### Styling
Binance tokens already in place — reuse `Card`, `Button`, `Input`, status-chip
(`state-badge`) patterns, the subtle filter/segmented-control treatment, and
`font-numeric` for any counts. Channel-type cards = `surface` + hairline +
hover `surface-2`, channel icon in a `bg-primary/10` tile.

**Frontend estimate: ~1.5-2 days.**

---

## Total estimate: ~2-3 days
Backend exposure + generalized load/delete (~0.5d) → API client (~0.5d) →
list + picker + forms (~1d) → settings/members/delete + QA (~0.5-1d).

## Open decisions for tomorrow
1. **v1 channel set** — confirm the recommended 7 (Telegram, WhatsApp Cloud,
   Bandwidth, Twilio, Website, API, Email), or trim to the priority ones
   (Telegram + WhatsApp first?).
2. **Location** — Settings → Bandejas (Chatwoot parity) vs a top-level
   "Canales" nav item. Recommend Settings parity.
3. **Webhook URLs** — after create, show the inbound webhook URL + verify token
   the user pastes into Meta/Telegram. Need to confirm the public URL shape per
   channel (from the webhook routers).

## Anchors
- Backend: `app/domains/inboxes/{router,service,models,schemas,presenters}.py`
- Chatwoot ref: `reference/chatwoot/app/javascript/dashboard/routes/dashboard/settings/inbox/`
- Parity context: `PLAN.parity-review.md` §7 (Inboxes = ⚠️ "Tier 1 of v2")
