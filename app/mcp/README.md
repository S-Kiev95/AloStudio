# AloStudio MCP Server

Exposes the AloStudio backend's conversation operations as MCP tools
so AI agents (Langchain / Langgraph / OpenAI Assistants / Claude
Desktop / etc.) can list, read and mutate conversations without
embedding an orchestrator in this process.

## Tool surface

24 tools across 5 modules. Permission scope per token: `read` <
`write` < `admin`.

### Health (`whoami`) — read

  * `whoami()` → returns the resolved account + scope. First call
    every agent makes to confirm wire + learn account context.

### Conversations — read + write

  * `list_conversations(status?, assignee_id?, page, per_page)` — read
  * `show_conversation(conversation_id, message_tail=10)` — read
  * `resolve_conversation(conversation_id)` — write
  * `reopen_conversation(conversation_id)` — write
  * `change_status(conversation_id, status)` — write
  * `change_priority(conversation_id, priority)` — write
  * `assign_agent(conversation_id, agent_id|null)` — write
  * `assign_team(conversation_id, team_id|null)` — write
  * `add_label(conversation_id, labels[])` — write
  * `remove_label(conversation_id, labels[])` — write
  * `get_ai_mode(conversation_id)` — read
  * `set_ai_mode(conversation_id, "auto"|"manual")` — write

### Messages — read + write

  * `list_messages(conversation_id, before_id?, limit=50)` — read
  * `show_message(message_id)` — read
  * `send_message(conversation_id, content, private=false)` — write
  * `add_private_note(conversation_id, content)` — write

### Contacts — read + write

  * `list_contacts(query?, page, per_page)` — read
  * `show_contact(contact_id)` — read
  * `set_contact_custom_attribute(contact_id, key, value)` — write
  * `set_conversation_custom_attribute(conversation_id, key, value)` — write

### Meta (labels + reports) — read

  * `list_labels()` — read
  * `get_account_summary(since_hours=168, business_hours=false)` — read
  * `get_live_metrics()` — read

## Auth

Every connection must carry an MCP token:

  * **HTTP transport** — `Authorization: Bearer <token>` header.
  * **stdio transport** — `MCP_BEARER_TOKEN` env var.

Tokens live in the `mcp_tokens` table (separate from
`access_tokens`). Each is account-scoped + carries a permission
`scope`. Mint via the service layer:

```python
from app.mcp.service import create_token

token = await create_token(
    session,
    account_id=42,
    name="auto-reply-agent",
    scope="write",  # read / write / admin
    user_id=1,      # optional — informational only
)
```

## Running

### As a stdio MCP server (Claude Desktop)

Set `MCP_BEARER_TOKEN` in the env block:

```jsonc
// ~/.claude_desktop_config.json
{
  "mcpServers": {
    "alostudio": {
      "command": "uv",
      "args": [
        "--directory", "C:/Users/Zeek/Desktop/AloStudio",
        "run", "python", "-m", "app.mcp"
      ],
      "env": {
        "MCP_BEARER_TOKEN": "<your-mcp-token>",
        "DATABASE_URL": "postgresql+asyncpg://alostudio:alostudio@localhost:5433/alostudio_test"
      }
    }
  }
}
```

### As an HTTP MCP server (remote agents)

The HTTP-server entry point isn't shipped yet — that's part of the
deployment-layer follow-up since it needs a TLS terminator,
rate-limiter, etc. For now, run via stdio or roll your own
`fastmcp run` invocation with HTTP transport.

## Architecture

```
┌─────────────────────────────────────┐
│ AloStudio backend                   │
│  ├─ FastAPI app (Chatwoot mirror)   │
│  ├─ AgentBot push (HMAC webhooks)   │
│  └─ MCP server (fastmcp) ──────────┐│
└────────────────────────────────────┼┘
                                     ▼
                          ┌──────────────────┐
                          │ MCP transport    │
                          │ (stdio │ http)   │
                          └──────────────────┘
                                     ▲
                  ┌──────────────────┼──────────────────┐
              ┌───────┐         ┌────────┐         ┌────────┐
              │ Auto- │         │ FAQ    │         │ Claude │
              │ reply │         │ classif│         │ Desktop│
              └───────┘         └────────┘         └────────┘
```

Tools call the service layer directly (`app/domains/*/service.py`) so
the full event cascade (reporting, automation, CSAT, AgentBot
relay, webhook delivery) fires naturally on each mutation.

## Adding new tools

1. Add an `async def` to one of `app/mcp/tools/*.py` (or create a new
   submodule).
2. Decorate it with `@mcp.tool(name=...)` then
   `@requires("read"|"write"|"admin")`.
3. Read context via `current_mcp_context()` — never accept
   `account_id` as an argument (the token's scope handles that).
4. Add a registration line to `app/mcp/tools/__init__.py`.
5. Write a test in `tests/integration/test_mcp_*.py` following the
   committed-fixture pattern.
