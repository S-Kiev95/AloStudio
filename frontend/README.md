# AloStudio Frontend

Next.js 15 (App Router) + React 19 + TypeScript dashboard for the AloStudio
FastAPI backend. Mirrors Chatwoot's OSS feature surface and adds the
project's own extensions (Instagram publishing, products catalogue, MCP
tokens, public Help Center).

## Quickstart

Prereqs: Node 20+, the FastAPI backend running on `http://localhost:8000`
(see the [root README](../README.md) for backend setup).

```bash
npm install
cp .env.example .env.local      # edit if your backend lives elsewhere
npm run dev                     # http://localhost:3000
```

For end-to-end / manual login, seed the demo admin (idempotent):

```bash
# from the repo root
DATABASE_URL="postgresql+asyncpg://alostudio:alostudio@localhost:5433/alostudio" \
    python scripts/seed_demo_account.py
# → demo@example.com / Password123!
```

## Stack

| Layer | Choice |
|---|---|
| Framework | Next.js 15, App Router, React 19 |
| Language | TypeScript (strict) |
| Styling | Tailwind 3.4 (no plugins) + semantic CSS variables for theming |
| Server state | TanStack Query 5 |
| UI state | Local React state + Zustand (when needed) |
| Forms | react-hook-form + zod |
| Realtime | Native WebSocket against the backend's ActionCable-compatible `/cable` |
| Markdown | react-markdown + remark-gfm (server-rendered, no client JS) |
| Unit tests | Vitest + Testing Library + MSW (41 tests) |
| E2E | Playwright (6 specs, runs against the real backend) |
| Theme | next-themes (system/light/dark via `.dark` class) |

## Architecture

### Layout

```
app/
  (auth)/             — login / forgot / reset (no auth required)
  accounts/
    [accountId]/      — dashboard shell (sidebar + topbar + theme)
      conversations/  — list + detail + reply (realtime)
      instagram/      — connection + publishing + comments
      products/       — catalogue CRUD
      reports/        — live counters + summary cards + timeseries chart
      help-center/    — admin CRUD for portals / categories / articles
      campaigns/      — ongoing + one-off campaigns
      settings/       — 12 sub-sections (labels, teams, macros, …, MCP tokens)
  hc/                 — PUBLIC Help Center (no auth, ISR, /robots.txt)
  api/
    auth/             — cookie-issuing route handlers (login, logout, …)
    backend/[…path]/  — BFF proxy → FastAPI with devise headers attached
```

### Auth: cookie ⇄ devise header bridge

The backend uses devise-token-auth (rotating tokens in
`access-token` / `client` / `uid` headers). The browser never touches
those headers directly:

1. The login form posts to `/api/auth/login` (a Next route handler).
2. That handler calls the backend's `/auth/sign_in`, captures the
   devise headers from the response, and stores them as **httpOnly
   cookies** (`alo_access_token` / `alo_client` / `alo_uid` /
   `alo_expiry`). The browser only receives `{accountId, user}`.
3. Subsequent API calls go through `/api/backend/[...path]` (the BFF
   proxy). That route reads the cookies and re-attaches them as devise
   headers before forwarding to FastAPI.

Why bother: the token sits in an httpOnly cookie → XSS can't read it,
and the devise header rotation still works because the BFF route
captures the new headers on each response.

### Public Help Center (ISR)

Routes under `/hc/<slug>` are completely public and server-rendered with
a 5-minute revalidate window. They call the backend directly
(`BACKEND_INTERNAL_URL`, server-side only) — no BFF, no auth headers.
Markdown is rendered server-side via `react-markdown` + `remark-gfm`,
so client JS for the article page is ~176 B.

`React.cache()` deduplicates portal/category fetches across the layout
and the page within a single request.

### Realtime

`useCable()` opens one WebSocket per signed-in session against
`NEXT_PUBLIC_CABLE_URL`. Authentication uses the `pubsub_token`
returned by `/api/v1/profile` (not cookies — WebSockets can't carry
custom headers in browsers). Cable events invalidate TanStack Query
caches so the relevant pages refetch.

## Environment

| Var | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_BASE` | `/api/backend` | Browser → BFF proxy. Keep same-origin so cookies are sent. |
| `BACKEND_INTERNAL_URL` | `http://localhost:8000` | Server-only: where the BFF proxy forwards to. |
| `NEXT_PUBLIC_CABLE_URL` | `ws://localhost:8000/cable` | WebSocket endpoint (browser connects directly). |
| `OPENAPI_URL` | `http://localhost:8000/openapi.json` | Only used by `npm run gen:api` (orval). |

`cp .env.example .env.local` and override as needed.

## Scripts

| Command | What it does |
|---|---|
| `npm run dev` | Dev server on :3000 (HMR, Tailwind JIT) |
| `npm run build` | Production build |
| `npm start` | Serve the production build |
| `npm run lint` | ESLint (`eslint-config-next`) |
| `npm run typecheck` | `tsc --noEmit` |
| `npm test` | Vitest run (unit + MSW) |
| `npm run test:watch` | Vitest watch mode |
| `npm run e2e` | Playwright (needs backend on :8000 + demo account seeded) |
| `npm run gen:api` | orval — codegen from the backend's OpenAPI schema |

## Bundle sizes

Production build, First Load JS column. The shell chunks are shared
across all routes (~102 kB). Anything above that is route-specific code.

| Route | Size | First Load JS |
|---|---:|---:|
| `/` | 176 B | 103 kB |
| `/accounts/[accountId]` (Inicio) | 176 B | 103 kB |
| `/accounts/[accountId]/conversations` | 4.54 kB | 126 kB |
| `/accounts/[accountId]/conversations/[id]` | 4.73 kB | 129 kB |
| `/accounts/[accountId]/instagram` | 5.53 kB | 147 kB |
| `/accounts/[accountId]/instagram/posts` | 8.75 kB | 130 kB |
| `/accounts/[accountId]/products` | 4.00 kB | 125 kB |
| `/accounts/[accountId]/reports` | 3.75 kB | 122 kB |
| `/accounts/[accountId]/help-center` | 4.60 kB | 129 kB |
| `/accounts/[accountId]/campaigns` | 1.99 kB | 127 kB |
| `/accounts/[accountId]/settings/*` (avg) | ~4 kB | ~125 kB |
| **Public `/hc/[slug]`** | 176 B | 106 kB |
| **Public `/hc/[slug]/articles/[articleSlug]`** | 176 B | 106 kB |

Notes:

* Public Help Center routes ship almost zero client JS — all the
  Markdown + layout work happens on the server.
* `/accounts/[accountId]/instagram` has the largest first-load (~147 kB)
  because it pulls in the channel-connect components + IG-specific
  query hooks; nothing alarming.
* All routes stay under 10 kB of route-specific JS — no
  bundle-analyzer flag-raising.

### Optional deep dive: `@next/bundle-analyzer`

```bash
npm install --save-dev @next/bundle-analyzer
```

Wrap `next.config.mjs`:

```js
import bundleAnalyzer from "@next/bundle-analyzer";
const withBundleAnalyzer = bundleAnalyzer({ enabled: process.env.ANALYZE === "true" });
export default withBundleAnalyzer({ /* …existing config… */ });
```

Then `ANALYZE=true npm run build` opens the treemap.

## Testing

### Unit / component (Vitest + MSW)

41 tests covering API hooks, helpers (time / errors / cable), and at
least one MSW-driven list view per CRUD module.

```bash
npm test
```

### End-to-end (Playwright)

6 specs in `tests/e2e/` driving Chromium against the real backend
and a seeded `demo@example.com` admin. Each test uses millisecond-
suffixed names so reruns don't collide on backend state.

```bash
# Terminal 1 — backend (from the repo root)
DATABASE_URL="postgresql+asyncpg://alostudio:alostudio@localhost:5433/alostudio" \
    python scripts/seed_demo_account.py     # idempotent
uvicorn app.main:app --port 8000 --reload

# Terminal 2 — frontend dev server (from frontend/)
npm run dev

# Terminal 3 — tests (from frontend/)
npm run e2e
```

Specs:

* `auth.spec.ts` — login flow, guard redirects, bad-password error
* `labels.spec.ts` — settings CRUD round-trip
* `help-center.spec.ts` — admin create → public ISR page renders
* `instagram-connect.spec.ts` — UI surface (does NOT hit Meta)

## Deploy

See [DEPLOY.md](./DEPLOY.md).
