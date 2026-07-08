# AloStudio

A **Chatwoot v4.13.0 (OSS) → FastAPI** byte-for-byte wire-parity migration,
extended with:

- an **Instagram Graph** module (publishing, comment moderation, webhooks,
  product catalogue, OAuth connection),
- an **MCP server** (FastMCP) that exposes the backend to AI agents, and
- a **Next.js** dashboard frontend (feature-parity port of the Chatwoot UI).

> **Branches:**
> | Branch | Contents |
> |---|---|
> | **`main`** | Backend (FastAPI) + Instagram module + MCP server + the merged v1 Next.js frontend (F.0–F.13). |
> | **`feat/v2`** | v2 work on top of `main`: Contacts, Agents admin, Notifications, the AI-integration polish (HTTP MCP transport, webhook retries, ai_mode), and the new e2e specs. |
>
> The v1 frontend was merged into `main`; `feat/v2` carries the latest
> milestones. See the **audit / fresh-session entry point** in the
> [Documentation index](#documentation-index) below.

---

## Architecture

```
                       ┌──────────────────────────┐
   Browser ───────────▶│  Next.js frontend         │   (feat/frontend-next)
                       │  • App Router + Tailwind  │
                       │  • httpOnly-cookie auth   │
                       │  • BFF proxy /api/backend │
                       └────────────┬─────────────┘
                                    │ devise headers (server-side)
                                    ▼
   AI agents ──(MCP)──▶ ┌──────────────────────────┐ ──▶ Postgres
                        │  FastAPI backend          │ ──▶ Redis
   Meta Graph ◀────────▶│  • domain-driven JSON API │      │
   (Instagram)          │  • devise-token-auth      │      ├─ ARQ worker (jobs + 5-min scheduler)
                        │  • ActionCable WS (realtime)      └─ MCP server (FastMCP)
                        └──────────────────────────┘
```

### Backend (`app/`, branch `main`)
- **Stack:** Python 3.12 · FastAPI · SQLModel · asyncpg · Alembic · ARQ ·
  FastMCP. Entry point `app.main:app`.
- **Domain-driven:** `app/domains/<domain>/{models,service,router,presenters,schemas}.py`
  (accounts, users/auth, inboxes, conversations, contacts, teams, labels,
  macros, automation, csat, reporting, campaigns, portals, webhooks,
  integrations, working_hours, the channel webhooks, **instagram**,
  **products**).
- **Auth:** devise-token-auth compatible — `access-token` / `client` / `uid`
  request headers (`app/core/deps.py`, `app/core/auth/`).
- **Realtime:** ActionCable-compatible WebSocket (`app/core/cable.py`) +
  Redis-backed broadcaster (`app/core/realtime.py`).
- **Async work:** ARQ worker (`app/workers/`) — Instagram publishing tasks
  + a `tick_5min` cron that fires scheduled posts.
- **Migrations:** Alembic (`alembic/versions/`).
- **Tests:** pytest markers `unit` / `integration` / `parity`
  (`reference/` holds the Chatwoot clone the parity tier compares against).

### Instagram module (`app/domains/instagram`, `app/domains/products`)
Publishing (image / video / reels / carousel / stories) with scheduling,
delete, comment moderation, webhook reception (comments / mentions /
story_insights + optional HMAC), a product catalogue linked to posts
(AI/CRM context), connection flows (Facebook Login OAuth, Instagram Login
OAuth, manual token), and MCP tools.
See [`app/domains/instagram/README.md`](app/domains/instagram/README.md),
[`PLAN.instagram-graph.md`](PLAN.instagram-graph.md) and
[`MANUAL-instagram-credenciales.md`](MANUAL-instagram-credenciales.md).

### MCP server (`app/mcp`)
FastMCP server exposing conversation/CRM + Instagram tools to external AI
agents (Bearer-token auth via the `mcp_tokens` table).
See [`app/mcp/README.md`](app/mcp/README.md).

### Frontend (`frontend/`, branch `feat/frontend-next`)
Next.js (App Router) + TypeScript + Tailwind + TanStack Query. Auth uses
**httpOnly cookies** set by Next route handlers; a same-origin **BFF proxy**
(`/api/backend/*`) re-attaches the devise headers server-side. Typed API
client generated from the backend OpenAPI (orval).
See [`frontend/README.md`](frontend/README.md),
[`PLAN.frontend-next.md`](PLAN.frontend-next.md) and
[`frontend/DESIGN-SYSTEM.md`](frontend/DESIGN-SYSTEM.md).

---

## Local development

**Prerequisites:** Docker (Desktop), Python 3.12 (`uv` recommended), Node 20+.

### 1. Infrastructure (Postgres + Redis + mail + S3)
```bash
docker compose up -d postgres redis mailhog minio
# Postgres → localhost:5433 · Redis → localhost:6380 · MailHog UI → :8025
```

### 2. Backend
```bash
uv sync                       # or: python -m venv .venv && pip install -e .
cp .env.example .env          # base config
#   put secrets (META_*, SMTP, etc.) in .env.local — gitignored
.venv/Scripts/python -m alembic upgrade head      # run migrations
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
# async worker (separate process; includes the 5-min scheduler):
.venv/Scripts/python -m arq app.workers.entrypoint.WorkerSettings
```
API docs at `http://localhost:8000/docs`, OpenAPI at `/openapi.json`.

### 3. Frontend (on `feat/frontend-next`)
```bash
git checkout feat/frontend-next
cd frontend
cp .env.example .env.local    # set BACKEND_INTERNAL_URL=http://localhost:8000
npm install
npm run gen:api               # generate the typed client (backend must be up)
npm run dev                   # http://localhost:3000
```

### 4. Tests
```bash
# backend
.venv/Scripts/python -m pytest -m unit
.venv/Scripts/python -m pytest -m integration   # needs Postgres + Redis
# frontend
cd frontend && npm test && npm run build
```

---

## Configuration (key env vars)

Secrets live in **`.env.local`** (gitignored); `.env` holds non-secret
defaults. See `.env.example` for the full list.

| Var | Purpose |
|---|---|
| `SECRET_KEY` | app secret (sessions, signed state) |
| `DATABASE_URL` / `DATABASE_URL_SYNC` | asyncpg (app) / psycopg (Alembic) |
| `REDIS_URL` / `ARQ_REDIS_URL` | realtime + ARQ queue |
| `SMTP_*` / `MAIL_FROM` | outbound email |
| `STORAGE_BACKEND` / `S3_*` | attachment storage |
| `IG_VERIFY_TOKEN` | Instagram webhook verify token |
| `META_APP_ID` / `META_APP_SECRET` | Facebook Login OAuth + webhook HMAC |
| `META_INSTAGRAM_APP_ID` / `_SECRET` | Instagram Login OAuth (no FB Page) |
| `META_OAUTH_REDIRECT_URI` | OAuth callback (matches the Meta app) |
| `META_GRAPH_API_VERSION` | pinned `v23.0` |
| `META_VERIFY_WEBHOOK_SIGNATURE` | enforce IG webhook HMAC (prod) |
| `META_CHECK_PUBLISHING_QUOTA` | pre-publish 24h quota check |

Per-account Instagram Page tokens + IG ids live on the `channel_instagram`
row, **never** in env.

---

## Deployment

- **Backend:** containerize and run `uvicorn app.main:app` (behind a process
  manager / multiple workers). Run **Alembic `upgrade head`** on each
  deploy. Run the **ARQ worker** as a separate process (it carries the
  5-minute scheduler that fires scheduled Instagram posts). Provide a
  managed **Postgres** + **Redis**. The ActionCable WebSocket endpoint must
  be reachable for realtime.
- **Frontend:** `next build` (use `output: 'standalone'` for Docker) or
  deploy to Vercel. Set `BACKEND_INTERNAL_URL` (server→backend, private) and
  keep `NEXT_PUBLIC_API_BASE=/api/backend`. Auth cookies are `Secure` in
  production.
- **MCP server:** run as a separate process (stdio for local agents, HTTP
  for remote) — see `app/mcp/README.md`.
- **Meta / Instagram (production):** the Meta app must be in **Live** with
  **App Review** approved for the IG scopes (`instagram_content_publish`,
  `instagram_manage_comments`, …) to let third-party accounts connect; a
  test account with a role in the app works without review. **Rotate** any
  token that was ever exposed.

---

## Documentation index

### For an audit / fresh session — start here
1. [`PLAN.parity-review.md`](PLAN.parity-review.md) — what's done vs
   Chatwoot, where the remaining gaps are. **The audit-base document.**
2. [`PLAN.frontend-v2.md`](PLAN.frontend-v2.md) — the v2 roadmap;
   all 9 sub-milestones marked ✅ as of the last commit.
3. [`INTEGRATIONS.md`](INTEGRATIONS.md) — external-agent contract
   (MCP + webhooks): payload shape, dual signature header, retry
   semantics, anti-loop guidance.
4. [`frontend/DEPLOY.md`](frontend/DEPLOY.md) — production deploy +
   MCP HTTP transport recipe (nginx + docker-compose sidecar).

### Roadmap + phase docs
- [`PLAN.md`](PLAN.md) — overall migration plan + phase index
- [`PLAN.frontend-next.md`](PLAN.frontend-next.md) — v1 frontend roadmap (closed)
- [`PLAN.frontend-v2.md`](PLAN.frontend-v2.md) — v2 roadmap (closed)
- [`PLAN.parity-review.md`](PLAN.parity-review.md) — Chatwoot OSS parity audit
- [`PLAN.instagram-graph.md`](PLAN.instagram-graph.md) — Instagram module
- [`PLAN.mcp-server.md`](PLAN.mcp-server.md) — MCP server design
- `PLAN.phase{1..10}.md` — per-phase backend porting plans

### Subsystem READMEs + contracts
- [`INTEGRATIONS.md`](INTEGRATIONS.md) — external-agent contract (MCP + webhooks)
- [`app/mcp/README.md`](app/mcp/README.md) — MCP tool surface + transport options
- [`app/domains/instagram/README.md`](app/domains/instagram/README.md) — Instagram pipeline
- [`frontend/README.md`](frontend/README.md) — frontend dev guide
- [`frontend/DEPLOY.md`](frontend/DEPLOY.md) — frontend deploy + MCP HTTP backend recipe
- [`frontend/DESIGN-SYSTEM.md`](frontend/DESIGN-SYSTEM.md) — token system + component conventions
- [`MANUAL-instagram-credenciales.md`](MANUAL-instagram-credenciales.md) — Meta credentials how-to
