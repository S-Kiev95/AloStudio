# AloStudio integrations

External-agent integration contract. Three surfaces:

1. **MCP server** — agents call tools to read + mutate state.
   Transports: `stdio` (local) and HTTP (remote).
2. **Webhooks** — AloStudio POSTs events to URLs you configure
   (account-level subscribers + per-inbox `AgentBot`).
3. **REST API** — Chatwoot-compatible surface for everything the MCP
   doesn't cover yet.

Pair (1) + (2) for an "Alicia-style" autonomous agent: the agent
discovers conversations + replies via MCP, and reacts to live events
(new messages, status changes) via webhooks pushed to its own
endpoint.

---

## 1. MCP server

### Transports

```bash
# Local — Claude Desktop, stdio-based clients
python -m app.mcp stdio

# Remote — exposed over HTTP for cross-host agents
python -m app.mcp http --host 0.0.0.0 --port 8765
#   → URL: http://<host>:8765/mcp
```

Put a TLS terminator (Caddy / nginx / Cloudflare) in front of the
HTTP transport in production. The fastmcp HTTP server does **not**
itself rate-limit or strip headers; treat it like any FastAPI app.

### Authentication

Every connection authenticates with a per-account Bearer token.
Create one from the dashboard:
**Settings → Tokens MCP → New token**, pick a scope, copy the token
once (it's hashed in the DB).

```http
Authorization: Bearer <mcp_token>
```

For stdio (no HTTP headers), set the token via env var:

```bash
export MCP_BEARER_TOKEN=<mcp_token>
```

Scopes — least privilege:

* `read` — list / show / search; cannot mutate.
* `write` — `read` + reply / assign / label / set ai_mode.
* `admin` — `write` + delete / token management.

A token resolves to one account; switching accounts means a new
token. The full 24-tool surface is documented in
[`app/mcp/README.md`](app/mcp/README.md).

### First call

Every agent should `whoami` on startup to confirm wire + scope:

```python
from fastmcp import Client
from fastmcp.client.auth import BearerAuth

async with Client("http://alostudio.example/mcp", auth=BearerAuth(token)) as c:
    info = (await c.call_tool("whoami", {})).structured_content
    # {"account_id": 7, "account_name": "Acme", "scope": "write",
    #  "user": {"id": 12, "name": "Alicia"}}
```

---

## 2. Webhooks

AloStudio POSTs events to two kinds of receivers:

* **Account webhooks** — global. `Settings → Webhooks → New`.
  Subscribe to any combination of `conversation_created`,
  `conversation_updated`, `conversation_status_changed`,
  `message_created`.
* **AgentBot webhooks** — inbox-scoped. `Settings → Bots → New`.
  Subscribed events are fixed (same list as account webhooks +
  `conversation_opened` / `conversation_resolved`).

Both share the **same envelope, headers, and signing**.

### Headers

| Header                  | Value                                                       | Notes                                  |
|-------------------------|-------------------------------------------------------------|----------------------------------------|
| `Content-Type`          | `application/json`                                          | UTF-8 JSON body.                       |
| `X-Chatwoot-Delivery`   | UUID, mirrors `event_id` in the body                        | Per-delivery; same value on a retry.   |
| `X-Chatwoot-Signature`  | `<hex>` — HMAC-SHA256 of the body bytes, secret = your hook | Legacy Chatwoot parity; bare hex.      |
| `X-AloStudio-Signature` | `sha256=<hex>` — same digest, GitHub-style prefix           | v2.7 modern alias. Prefer this one.    |

If your `secret` is empty (Chatwoot allows this for AgentBots),
both signature headers are empty strings — verify them as authentic
absence-of-signature.

### Body shape

Every body carries:

* `event` — e.g. `message_created`.
* `event_id` — UUID matching `X-Chatwoot-Delivery`. **Use this as
  your dedupe key**: AloStudio reuses it across retries (v2.9).

Plus event-specific fields:

#### `message_created` (most-used)

```json
{
  "event": "message_created",
  "event_id": "8b0d2cf2-…-…",
  "id": 4218,
  "content": "Necesito ayuda con mi pedido",
  "content_type": "text",
  "message_type": "incoming",
  "sender_type": "contact",
  "sender_id": 991,
  "private": false,
  "source_id": null,
  "content_attributes": {},
  "additional_attributes": {},
  "created_at": 1717326000,
  "conversation": {
    "id": 7113,
    "account_id": 7,
    "inbox_id": 12,
    "contact_id": 991,
    "assignee_id": null,
    "status": "open",
    "priority": null,
    "display_id": 42,
    "uuid": "…"
  }
}
```

`sender_type` is the lowercase STI label — one of:

| Value        | Who sent the message                                                |
|--------------|---------------------------------------------------------------------|
| `contact`    | The end user / customer (incoming).                                 |
| `user`       | A human agent reply (outgoing).                                     |
| `agent_bot`  | A bot reply via MCP or webhook reply path (outgoing).               |
| `api`        | Outgoing message produced by an API-channel POST with no human user.|
| `null`       | Edge case — channel layer didn't stamp a sender; treat as unknown.  |

#### `conversation_*` events

Body = the conversation slice (`id`, `account_id`, `inbox_id`,
`contact_id`, `assignee_id`, `status`, `priority`, `display_id`,
`uuid`, `created_at`, plus `additional_attributes` /
`custom_attributes`) + `event` + `event_id`. Update events also
carry `changed_attributes` when the dispatcher emitted them.

### Verifying the signature

Compute HMAC-SHA256 over the **raw body bytes** (don't parse JSON
first — re-serializing breaks the digest) with your hook's secret:

```python
import hashlib, hmac
expected = hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()
ok = hmac.compare_digest(
    expected,
    request.headers["X-AloStudio-Signature"].removeprefix("sha256="),
)
# or, for legacy receivers:
ok_legacy = hmac.compare_digest(expected, request.headers["X-Chatwoot-Signature"])
```

```typescript
// Node.js
import { createHmac, timingSafeEqual } from "node:crypto";
const expected = createHmac("sha256", secret).update(rawBody).digest("hex");
const got = req.headers["x-alostudio-signature"]?.replace(/^sha256=/, "");
const ok = !!got && timingSafeEqual(Buffer.from(expected), Buffer.from(got));
```

```bash
# Quick shell sanity check
echo -n "$BODY" | openssl dgst -sha256 -hmac "$SECRET"
# compare to X-AloStudio-Signature (strip the "sha256=" prefix)
```

### Anti-loop guidance

`message_created` fires for **both** incoming and outgoing messages
(Chatwoot parity). If your receiver writes back replies via MCP, you
**must** filter:

```python
if body["message_type"] != "incoming":
    return  # don't reply to your own reply
```

A bot replying via the AgentBot webhook contract should also drop
messages it sent itself:

```python
if body["sender_type"] == "agent_bot":
    return
```

### Retry semantics

**Durable retry (v2.9+).** Delivery runs on the ARQ queue with a
10-second HTTP timeout per attempt. On a non-2xx response **or** a
transport error the delivery is retried with exponential backoff:

| Attempt | On failure, wait |
|--------:|------------------|
| 1 (initial) | 5 s |
| 2 | 30 s |
| 3 | 5 min |
| 4 | 30 min |
| 5 | **dead-letter** — quarantined, no further attempts |

So a receiver gets up to **5 delivery attempts** (initial + 4 retries)
spanning ~35 minutes before AloStudio gives up and records the failure
in a per-receiver dead-letter log (`webhook_dead_letters`) that an
operator can inspect.

The same `event_id` is reused across all retries (and mirrored in the
`X-Chatwoot-Delivery` header), so a receiver that **dedupes on
`event_id` is automatically retry-safe** — a duplicate delivery after a
slow/failed ACK is a no-op on your side.

> Deployments without an ARQ worker fall back to a single inline
> attempt; a terminal failure there still writes a dead-letter row, so
> the operator-visible signal is identical.

### Recommended receiver checklist

* [ ] Verify `X-AloStudio-Signature` (constant-time comparison).
* [ ] Dedupe on `event_id`.
* [ ] Drop `message_type != "incoming"` if you reply automatically.
* [ ] Drop `sender_type == "agent_bot"` for bot-reply paths.
* [ ] Respond `200 OK` quickly; do work async.
* [ ] Tolerate fields you don't know — payloads are additive.

---

## 3. REST API

Chatwoot v4.13.0-compatible. Auth: `api_access_token` header on
account routes, devise-token-auth (`access-token` / `client` /
`uid`) for user routes. Same shape as the Chatwoot OSS docs at
<https://www.chatwoot.com/developers/api/> — modulo the deferred
endpoints listed in [`PLAN.parity-review.md`](PLAN.parity-review.md).

Prefer the MCP for AI-agent integrations: it's higher-level,
permission-scoped, and the tool surface is curated for agent use.

---

## Local testing tips

* Boot the test backend with the dev compose:
  `docker compose up -d postgres redis`, then `uvicorn app.main:app
  --reload`.
* Use `ngrok http 8000` to expose a tunnel; point your account
  webhook at `https://<id>.ngrok.io/<your-path>` and trigger an
  inbound message to see the body land.
* For MCP, the easiest smoke test is the in-process `fastmcp.Client`:

  ```python
  from app.mcp.server import build_server
  from fastmcp import Client
  async with Client(build_server()) as c:
      print(await c.call_tool("whoami", {}))
  ```

  No HTTP, no token resolution — useful for iterating on tool code.
