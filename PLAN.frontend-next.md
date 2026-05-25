# Frontend — Next.js dashboard (mirror of the Chatwoot UI)

**Branch:** `feat/frontend-next`

**Goal:** A Next.js (React + TypeScript) frontend with **feature parity**
to Chatwoot's dashboard, consuming the AloStudio FastAPI backend. Same
"espejo" strategy as the backend port — but since Chatwoot's UI is Vue,
this is a **behavioural port screen-by-screen** (not a 1:1 component
copy). The Chatwoot Vue app is the reference for *what each screen does*;
we re-implement it in React.

> Reference UI: `reference/chatwoot/app/javascript/` (dashboard views,
> store modules, API endpoints) — read for behaviour, not code.

---

## Why this works with Next (rendering split)

The dashboard is an **authenticated, highly-interactive SPA** → render it
**client-side** (App Router client components behind an auth guard); SSR
buys little there. Reserve Next's SSR/SSG for the **public, SEO-relevant**
surfaces:

| Surface | Rendering |
|---|---|
| Dashboard (conversations, contacts, settings, IG publishing) | CSR (client components) |
| Login / signup / password reset | SSR/SSG (light) |
| **Help Center (portals)** — public, indexable | SSG / ISR |
| Marketing / landing (if any) | SSG |

---

## Stack

| Concern | Choice | Why |
|---|---|---|
| Framework | **Next.js (App Router) + TypeScript** | user's choice; CSR dashboard + SSG public |
| Styling | **Tailwind CSS** | matches Chatwoot v4's design system → fast parity |
| UI primitives | **shadcn/ui** (Radix + Tailwind) | accessible components, own the code |
| Server state | **TanStack Query** | caching, mutations, optimistic updates |
| Client/UI state | **Zustand** | lightweight (Vuex/Pinia equivalent) |
| API layer | **OpenAPI codegen** (`orval` or `openapi-typescript`) from FastAPI `/openapi.json` | typed client + React Query hooks, **wire parity for free** |
| Forms | **react-hook-form + zod** | validation mirrors backend schemas |
| Realtime | **`@rails/actioncable`** + a React hook | the backend speaks the ActionCable protocol (`app/core/cable`) |
| i18n | `next-intl` (deferred) | Chatwoot is multilingual; start English-only |
| Testing | **Vitest + React Testing Library**, **MSW**, **Playwright** | unit/component, API mocks, e2e |

---

## Cross-cutting foundations (build first, in F.0/F.1)

### API client + types
- Generate types/hooks from the backend `GET /openapi.json` (run codegen
  as an npm script). Re-run when the API changes. This is the single
  biggest accelerator + guarantees the contract.
- Thin fetch wrapper that injects auth headers + base URL
  (`NEXT_PUBLIC_API_BASE`), normalises the backend's error envelopes
  (`{message}` / `{error}` / `{errors:[]}`), and redirects to login on 401.

### Auth (devise-token-auth) — **httpOnly cookies (decided)**
- The backend authenticates via headers **`access-token`, `client`,
  `uid`** (+ `expiry`). Login (`POST /auth/sign_in`) returns them.
- Backend does **not** rotate per request (`change_headers_on_each_request
  = false`), so the `(client, access-token)` pair is **stable after
  login** — refresh only on sign-in / password reset.
- **Storage = httpOnly cookies** set by Next **Route Handlers**
  (`app/(auth)/.../route.ts`): the browser never sees the tokens (XSS-
  safe). The login route handler calls the backend `/auth/sign_in`,
  reads the 3 devise headers, and sets them as httpOnly cookies. A small
  server-side adapter (route handler / server action **or** a BFF proxy
  under `app/api/*`) reads those cookies and re-attaches them as the
  custom devise **headers** on each backend call (devise uses headers,
  not cookies — the cookie↔header bridge is the adapter's job).
- Auth guard via App Router **middleware** (checks the cookie) → redirect
  unauthorised users to `/login`. Multi-account: account id lives in the
  route (`/accounts/{accountId}/...`), mirroring the backend's scoping.

### Realtime
- One ActionCable connection; subscribe to the account/conversation
  channels. A `useChannel` hook bridges WS events → TanStack Query cache
  invalidation (new message, conversation status change, assignment).

---

## Repo layout — **monorepo subdir (decided)**

`frontend/` lives in this repo (shared OpenAPI, one place to version):

```
frontend/                     # Next app (its own package.json / node)
  app/                        # App Router
    (auth)/login, signup, ...
    (dashboard)/accounts/[accountId]/
        conversations/ contacts/ inboxes/ instagram/ products/
        reports/ settings/ ...
    (public)/help/[slug]/     # SSG help center
  lib/api/                    # generated client + fetch wrapper
  lib/auth/  lib/realtime/  lib/store/
  components/ui/              # shadcn components
  components/<domain>/
  tests/  e2e/
```

---

## Milestones

> **v1 scope (decided):** F.0, F.1, F.2, F.3, F.5, F.6 — login + shell +
> conversations (with realtime) + Instagram connection + publishing. The
> rest (F.4, F.7–F.12) is v2. v1 makes the Instagram feature usable
> end-to-end early.

### F.0 — Project setup  · **v1**
- [ ] `frontend/` Next App Router + TS + Tailwind + shadcn/ui.
- [ ] TanStack Query provider, Zustand store skeleton, env config.
- [ ] OpenAPI codegen wired (`npm run gen:api` → typed client/hooks).
- [ ] Fetch wrapper (auth headers, error normaliser, 401 redirect).
- [ ] Base layout + theme + CI (lint/typecheck/test).

### F.1 — Auth  · **v1**
- [ ] Login, signup, email confirmation, password reset/forgot.
- [ ] Token storage + attach + 401 handling; auth guard; logout.
- [ ] Account bootstrap (`/profile`), account switcher.

### F.2 — App shell  · **v1**
- [ ] Sidebar + topbar + routing under `/accounts/[accountId]`.
- [ ] Agent profile, availability/status, notifications stub.

### F.3 — Conversations (core)  · **v1**
- [ ] Inbox/folder list + conversation list with filters
      (status / assignee / team / labels / inbox).
- [ ] Conversation view: message thread, reply box (incl. private notes),
      attachments, status / priority / assignee / team / labels.
- [ ] **Realtime**: live new-message + conversation updates via WS.

### F.4 — Contacts  · v2
- [ ] Contact list + search, contact detail, custom attributes,
      contact-inbox / conversations history.

### F.5 — Inboxes + channel connection  · **v1**
- [ ] Inbox CRUD + members + settings.
- [ ] **Instagram connection UI** — "Connect" buttons for Facebook Login
      + Instagram Login (hit `connect/start` / `start_instagram`), the
      manual-token form, and the capability view (`login_type`,
      `can_delete_media`).

### F.6 — Instagram publishing (the new extension)  · **v1**
- [ ] Composer: image / video / reels / carousel / stories + caption.
- [ ] Scheduling (`scheduled_for`) + a queue/calendar of pending posts.
- [ ] Post list + detail (state, permalink, containers, errors).
- [ ] Link products (`product_ids`) in the composer.
- [ ] Comments moderation panel (list / reply / hide / delete).

### F.7 — Products catalogue
- [ ] Product CRUD UI; product picker reused by the IG composer.

### F.8 — Reports
- [ ] Overview + summary cards + timeseries + live metrics.

### F.9 — Settings
- [ ] Teams, labels, macros, automation rules, canned responses,
      working hours, agent bots, integrations, webhooks,
      custom attributes, CSAT.

### F.10 — Help Center (portals)
- [ ] Admin CRUD (portals / categories / articles).
- [ ] **Public SSG/ISR site** (slug-keyed, published-only) for SEO.

### F.11 — Campaigns
- [ ] One-off + ongoing campaign CRUD.

### F.12 — Hardening + close
- [ ] Playwright e2e on the core flows (login → conversation → reply;
      IG connect → publish → comment).
- [ ] Perf pass, error boundaries, empty/loading states, a11y.
- [ ] README + deploy (Vercel or Docker) + point at the FastAPI backend.

### F.13 — Chatwoot UI parity review

The frontend analog of the backend's `parity` pytest tier — but
**functional/behavioural**, not byte-for-byte (we chose React + our own
design system, so this is *feature* parity, not a pixel clone). Uses the
reference Chatwoot already wired in `docker-compose.yml`
(`--profile reference` → `chatwoot-ref` on `127.0.0.1:3001`).

- [ ] **Feature-parity matrix** — a screen-by-screen checklist mapping
      every Chatwoot dashboard screen/feature → AloStudio status
      (present / equivalent behaviour / gaps). The documentary parity
      record. Commit as `docs/ui-parity.md`.
- [ ] **Behavioural e2e parity (Playwright)** — the same user journeys
      (login → conversation list → open → reply → message appears →
      resolve; IG connect → publish → comment) run against **both** the
      Chatwoot reference (`:3001`) and AloStudio (`:3000`), asserting
      equivalent outcomes (framework-agnostic, not DOM-identical).
- [ ] **Visual side-by-side** — Playwright screenshots of each screen in
      both apps as a **design-review aid** (not an automated pixel diff —
      different frameworks/design make pixel diffing pure noise).
- [ ] Triage the matrix gaps into follow-up tasks.

> Scope note: this is **functional + behavioural + visual-review** parity.
> A pixel-perfect Chatwoot clone is explicitly out of scope (it would
> contradict the AloStudio design system). Revisit only if the product
> decision changes.

---

## Decisions (locked)
1. **Repo:** ✅ monorepo `frontend/` subdir in this repo.
2. **Token storage:** ✅ httpOnly cookies via Next Route Handlers
   (cookie↔devise-header adapter on the server side).
3. **v1 scope:** ✅ F.0–F.3 + F.5–F.6 (core + Instagram end-to-end).
   F.4 + F.7–F.13 = v2.
4. **Design fidelity:** ✅ resolved — AloStudio's **own design system**
   (`frontend/DESIGN-SYSTEM.md`) on the same information architecture as
   Chatwoot; **not** a pixel clone. F.13 parity is therefore
   functional/behavioural, not pixel-perfect.

---

## Commit style
`fe.<n>: <area>: <short summary>` — one (or few) commits per milestone,
mirroring the backend's `phaseN` / `ig.N` convention.
