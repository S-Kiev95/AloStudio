# Deploying the AloStudio frontend

The frontend is a standard Next.js 15 app, but it has three
deployment-shape constraints worth noting:

1. **It needs to reach the FastAPI backend over the network.** The
   browser hits the same-origin BFF proxy (`/api/backend/[...path]`),
   so the proxy's Node runtime needs `BACKEND_INTERNAL_URL` pointing
   at the backend (internal cluster URL, ngrok tunnel, whatever).
2. **The public Help Center (`/hc/<slug>`) uses ISR.** Pick a host
   that supports per-request server rendering + cache revalidation
   (Vercel, Fly.io, Render, Docker on your own infra — all fine).
   Static-only hosts (S3 + CloudFront, GitHub Pages) won't work.
3. **WebSockets.** The browser connects directly to the backend at
   `NEXT_PUBLIC_CABLE_URL`. Whichever proxy sits in front of the
   backend needs WebSocket passthrough (this is the default on
   Vercel, Fly, Render, traefik, nginx with `proxy_http_version 1.1`,
   etc.).

## Option 1 — Vercel (recommended for the dashboard)

Best fit when the backend is reachable from the public internet (with
or without auth at the network edge — devise tokens cover app auth).

```bash
# from the repo root
vercel --cwd frontend
```

Project settings:

* **Build Command:** `npm run build`
* **Output Directory:** Next.js default (leave blank)
* **Install Command:** `npm install`
* **Root Directory:** `frontend`

Environment variables to set in the Vercel dashboard:

```
BACKEND_INTERNAL_URL=https://api.midominio.com
NEXT_PUBLIC_API_BASE=/api/backend
NEXT_PUBLIC_CABLE_URL=wss://api.midominio.com/cable
```

Notes:

* `BACKEND_INTERNAL_URL` is server-only. Set it on Vercel, **don't**
  prefix with `NEXT_PUBLIC_`.
* If the backend is behind Vercel itself, set
  `BACKEND_INTERNAL_URL=https://api.midominio.com` and Vercel's edge
  network will proxy the BFF requests over the wire normally.
* Free + Hobby plans throttle server-component rendering at high
  concurrency; the `/hc/<slug>` ISR cache (300 s) keeps that load tame.

## Option 2 — Docker (self-host)

Best fit when the frontend ships alongside the backend behind your own
ingress (nginx/traefik) and you control the network. Standard Next.js
standalone output keeps the image small (~150 MB).

`frontend/next.config.mjs` already exports `output: "standalone"` —
if not, add it:

```js
export default {
  output: "standalone",
};
```

Then drop a `frontend/Dockerfile`:

```dockerfile
# syntax=docker/dockerfile:1

# --- deps ---
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# --- builder ---
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# --- runner ---
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000

# Standalone output: copy only what's needed at runtime
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000
CMD ["node", "server.js"]
```

Build + run:

```bash
docker build -t alostudio-frontend:latest frontend
docker run --rm -p 3000:3000 \
  -e BACKEND_INTERNAL_URL=http://backend:8000 \
  -e NEXT_PUBLIC_API_BASE=/api/backend \
  -e NEXT_PUBLIC_CABLE_URL=wss://api.midominio.com/cable \
  --network alostudio-network \
  alostudio-frontend:latest
```

`BACKEND_INTERNAL_URL=http://backend:8000` assumes the FastAPI service
is reachable on the same Docker network (the `backend` hostname is the
container name). Adjust for your cluster.

### docker-compose snippet

```yaml
services:
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      BACKEND_INTERNAL_URL: http://backend:8000
      NEXT_PUBLIC_API_BASE: /api/backend
      NEXT_PUBLIC_CABLE_URL: wss://api.midominio.com/cable
    depends_on:
      - backend
    networks:
      - alostudio
```

## Production checklist

Before pointing real users at it:

* [ ] Rotate `BACKEND_INTERNAL_URL` to HTTPS — the BFF proxy strips
      hop-by-hop headers but tokens still travel over the wire.
* [ ] Confirm `NEXT_PUBLIC_CABLE_URL` uses `wss://` (TLS).
* [ ] Confirm `app/robots.ts` allows `/hc/` and disallows
      `/accounts/` (the default we ship is right; check after any
      changes).
* [ ] Set up an error sink. The error boundaries
      (`app/error.tsx`, `app/accounts/[accountId]/error.tsx`,
      `app/hc/[slug]/error.tsx`) currently `console.error` —
      swap that for Sentry / Datadog / etc.
* [ ] If self-hosting the public Help Center on a custom domain
      (Chatwoot's `Portal.custom_domain` feature), terminate TLS
      at your ingress and route `/<slug>` → frontend `/hc/<slug>`.
      Currently the ISR cache key is the path, so a host-only
      rewrite is fine.
* [ ] Optional: enable Vercel Analytics / Speed Insights or your
      RUM of choice. The shell is ~102 kB First Load JS so Lighthouse
      Performance should be ≥ 95 on a clean device.

## Smoke checks after deploy

```bash
# 1. Login route handler reachable (BFF up)
curl -s -o /dev/null -w "%{http_code}\n" \
  -X POST https://app.midominio.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"…"}'
# expect 200 (or 401 with valid envelope)

# 2. Public Help Center renders without auth
curl -s -o /dev/null -w "%{http_code}\n" \
  https://app.midominio.com/hc/<slug>
# expect 200, or 404 if slug is wrong

# 3. robots.txt looks right
curl -s https://app.midominio.com/robots.txt
```

## Rollback

Both Vercel and the Docker recipe ship immutable artifacts (Vercel by
build id, Docker by image tag). Rolling back is "promote previous
deployment" / "redeploy previous image" — the database is owned by the
backend, so frontend rollbacks are safe.

---

## MCP HTTP transport (backend, v2.7+)

The MCP server can run alongside the FastAPI app for AI agents that
prefer HTTP over stdio (the stdio transport is for Claude Desktop /
local-loop dev). Same `build_server()`, same `AuthMiddleware`, same
tool surface — just a different wire protocol.

### Launching

```bash
# Foreground for testing
python -m app.mcp http --host 0.0.0.0 --port 8765

# Production (systemd unit / docker container)
python -m app.mcp http --host 127.0.0.1 --port 8765 --path /mcp
```

Bind to `127.0.0.1` and put a TLS terminator (nginx / Caddy / Traefik)
in front. The MCP transport speaks **streamable HTTP** — modern
fastmcp clients expect this; older `http`-only clients won't work.

### Auth

Agents pass `Authorization: Bearer <mcp_token>` on every request.
Tokens are issued from the dashboard at `Settings → Tokens MCP`
(`/accounts/{id}/settings/mcp_tokens`) and resolve to one account
plus a scope (`read` / `write` / `admin`).

### Reverse proxy recipe (nginx)

```nginx
# /etc/nginx/conf.d/mcp.conf
upstream mcp_backend {
    server 127.0.0.1:8765;
    keepalive 16;
}

server {
    listen 443 ssl http2;
    server_name mcp.midominio.com;
    ssl_certificate     /etc/letsencrypt/live/mcp.midominio.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mcp.midominio.com/privkey.pem;

    # MCP streamable-http needs HTTP/1.1 + long timeouts for tool
    # invocations that run long (e.g. ``list_conversations`` over a
    # busy account).
    location /mcp {
        proxy_pass         http://mcp_backend;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        # Pass the Authorization header through unmodified — the MCP
        # auth middleware reads it via fastmcp's get_http_headers.
        proxy_set_header   Authorization     $http_authorization;
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
        proxy_buffering    off;  # streamable-http expects flush-as-you-go
    }
}
```

Connect to it with a fastmcp client:

```python
from fastmcp import Client
from fastmcp.client.auth import BearerAuth

async with Client(
    "https://mcp.midominio.com/mcp",
    auth=BearerAuth("<your-mcp-token>"),
) as client:
    result = await client.call_tool("whoami", {})
    print(result.structured_content)
```

### docker-compose snippet (MCP HTTP service)

If you containerise the backend, add a sidecar service for the MCP
HTTP transport so it scales independently from the FastAPI workers:

```yaml
services:
  mcp-http:
    image: alostudio-backend:latest      # same image as the API
    command:
      ["python", "-m", "app.mcp", "http",
       "--host", "0.0.0.0", "--port", "8765", "--path", "/mcp"]
    environment:
      DATABASE_URL:  ${DATABASE_URL}
      REDIS_URL:     ${REDIS_URL}
      # No MCP_BEARER_TOKEN — HTTP transport reads the header instead
    ports:
      - "127.0.0.1:8765:8765"
    restart: unless-stopped
```

### Webhook receiver requirements (v2.7+)

External agents that subscribe to AloStudio webhooks (account-level
or per-bot) need to:

* Verify either `X-Chatwoot-Signature: <hex>` (legacy bare-hex) **or**
  `X-AloStudio-Signature: sha256=<hex>` (GitHub-style — recommended
  for new integrations). Same HMAC-SHA-256 digest over the raw body
  bytes, keyed on the webhook/bot secret.
* Dedupe by `event_id` in the JSON body (mirrors the
  `X-Chatwoot-Delivery` header).
* Filter `message_type === "incoming"` if they only want inbound
  customer messages — the webhook fires for both directions per
  Chatwoot parity.
* Tolerate retries: v2.9 retries 5s / 30s / 5min / 30min on non-2xx
  or transport errors before quarantining in `webhook_dead_letters`.

See `INTEGRATIONS.md` at the repo root for the full payload shape +
HMAC verification snippets in Python / Node / Go.
