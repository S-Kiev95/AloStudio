# AloStudio frontend (Next.js)

Next.js (App Router + TypeScript) dashboard — a feature-parity port of
the Chatwoot UI against the AloStudio FastAPI backend. See
[`../PLAN.frontend-next.md`](../PLAN.frontend-next.md) for the roadmap.

## Stack
Next 15 (App Router) · React 19 · TypeScript · Tailwind CSS ·
TanStack Query (server state) · Zustand (UI state) · orval (OpenAPI
codegen) · react-hook-form + zod · Vitest + Testing Library + MSW ·
Playwright (e2e).

## Getting started
```bash
cd frontend
cp .env.example .env.local        # set BACKEND_INTERNAL_URL etc.
npm install
npm run gen:api                   # generate the typed API client (backend must be reachable)
npm run dev                       # http://localhost:3000
```

## Scripts
| Script | Purpose |
|---|---|
| `npm run dev` | dev server |
| `npm run build` / `start` | production build / serve |
| `npm run lint` / `typecheck` | eslint / `tsc --noEmit` |
| `npm test` | Vitest unit/component tests |
| `npm run e2e` | Playwright end-to-end |
| `npm run gen:api` | regenerate `lib/api/generated/` from the backend OpenAPI |

## Architecture (F.0 foundations)
- **Auth = httpOnly cookies.** The login route handler (F.1) calls the
  backend `/auth/sign_in`, reads the devise headers (`access-token` /
  `client` / `uid`), and stores them as httpOnly cookies. The browser
  never sees the tokens.
- **BFF proxy** (`app/api/backend/[...path]`): the browser calls this
  same-origin proxy; it reads the auth cookies and re-attaches them as
  the devise **headers** before forwarding to the FastAPI backend
  (`BACKEND_INTERNAL_URL`). The cookie↔header bridge.
- **API layer**: orval generates typed TanStack Query hooks from the
  backend OpenAPI; they call the `apiFetch` mutator (`lib/api/fetcher.ts`)
  which targets the proxy and normalises error envelopes.
- **Auth guard**: `middleware.ts` redirects unauthenticated users away
  from `/accounts/*`.

## Layout
```
app/              App Router (pages, layouts, route handlers)
  api/backend/    BFF proxy to FastAPI
lib/api/          fetcher (orval mutator) + errors + generated/ (gitignored)
lib/auth/         cookie / header names
lib/store/        Zustand UI store
lib/query.ts      TanStack QueryClient factory
middleware.ts     auth guard
```
