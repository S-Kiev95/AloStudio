# AloStudio MCP Server

Exposes the AloStudio backend's conversation operations as MCP tools
so AI agents (Langchain / Langgraph / OpenAI Assistants / Claude
Desktop / etc.) can list, read and mutate conversations without
embedding an orchestrator in this process.

## Tool surface

One module per area in `app/mcp/tools/` (the code is the full list;
this page names the main ones). Permission scope per token: `read` <
`write` < `admin`. A service error (422 with a message) reaches the
client as that message, through `requires`.

### Health (`whoami`) — read

  * `whoami()` → returns the resolved account + scope. First call
    every agent makes to confirm wire + learn account context.

### Conversations — read + write

  * `list_conversations(status?, assignee_id?, page, per_page)` — read
  * `create_conversation(inbox_id, contact_id, message?, assignee_id?, team_id?)`
    — write. WhatsApp uses the contact's phone; Instagram, Messenger and
    Telegram only continue a contact who wrote first.
  * `show_conversation(conversation_id, message_tail=10)` — read
  * `resolve_conversation(conversation_id)` — write
  * `reopen_conversation(conversation_id)` — write
  * `change_status(conversation_id, status)` — write
  * `change_priority(conversation_id, priority)` — write
  * `assign_agent(conversation_id, agent_id|null)` — write
  * `assign_team(conversation_id, team_id|null)` — write
  * `add_label(conversation_id, labels[])` — write
  * `remove_label(conversation_id, labels[])` — write
  * `get_ai_mode(conversation_id)` — read; returns
    `{ai_mode: bool, ai_assignee: str|null}`.
  * `set_ai_mode(conversation_id, on, ai_assignee?)` — write; sets the
    takeover flag and (optionally) stamps which AI is on duty. Empty
    `ai_assignee` clears the slot. Dispatches `conversation.updated`
    so live dashboards refresh. While `ai_mode=true` the
    automation-rule listener stands down on this conversation.

### Messages — read + write

  * `list_messages(conversation_id, before_id?, limit=50)` — read
  * `show_message(message_id)` — read
  * `send_message(conversation_id, content?, private=false, attachments?)`
    — write; `attachments: [{"url": "https://…", "file_type": "image"}]`
  * `list_whatsapp_templates(inbox_id)` — read, approved ones only
  * `send_whatsapp_template(conversation_id, name, language, body_params?)`
    — write; the way to write after WhatsApp's 24 h window
  * `list_catalog_products()` — read, products of the Meta catalogue that
    can be sent
  * `send_whatsapp_products(conversation_id, product_ids, body?, header?)`
    — write; one product card or a list (up to 30), within the 24 h window
  * `add_private_note(conversation_id, content)` — write

### Contacts — read + write

  * `list_contacts(query?, page, per_page)` — read
  * `show_contact(contact_id)` — read
  * `create_contact(name, email?, phone_number?, identifier?, custom_attributes?)` — write
  * `update_contact(contact_id, name?, email?, phone_number?, identifier?)` — write
  * `set_contact_custom_attribute(contact_id, key, value)` — write
  * `set_conversation_custom_attribute(conversation_id, key, value)` — write

### Meta (account lookups, labels, reports)

  * `list_inboxes()`, `list_agents()`, `list_teams()` — read; the ids
    the other tools ask for
  * `list_canned_responses(search?)` — read
  * `list_labels()` — read
  * `create_label(title, description?, color?)` — write
  * `get_report_by(group_by: agent|team|inbox, from?, to?)` — read
  * `get_csat(from?, to?, rating?, page)` — read
  * `get_account_summary(since_hours=168, business_hours=false)` — read
  * `get_live_metrics()` — read

### Publishing and media

  * `list_publication_channels()`, `list_media()`, `list_publications()` — read
  * `show_publication(publication_id)` — read
  * `create_publication(...)`, `update_publication(...)`,
    `retry_publication(publication_id)`, `cancel_publication(publication_id)` — write
  * `upload_media(url, filename?)` — write; copies a public https file
    into the media library (outbound guard, size limits)
  * `get_publishing_analytics(from?, to?, channel_id?)` — read

### CRM sales pipeline

  * `list_pipelines()`, `list_opportunities(pipeline_id?, contact_id?,
    owner_id?, status?, query?)`, `list_crm_activities(...)` — read
  * `create_opportunity(title, ...)`, `update_opportunity(opportunity_id,
    stage_id?, ...)` (moving to a won/lost stage closes it) — write
  * `create_crm_activity(title, kind?, due_at?, ...)`,
    `update_crm_activity(activity_id, done?, ...)` — write

### Campaigns

  * `list_campaigns()`, `get_campaign_result(campaign_id)` — read
  * `create_campaign(title, inbox_id, contact_ids, message, scheduled_at,
    template_name?, template_language?, template_params?)` — write; one-off,
    WhatsApp needs an approved template

### Macros, catalogue and appointments

  * `list_macros()` — read; `execute_macro(macro_id, conversation_ids)` — write
  * `create_product(...)`, `update_product(product_id, ...)` — write
  * `update_appointment(appointment_id, title?, starts_at?, ends_at?,
    product_id?, notes?)` — write

### Account configuration (`admin` scope)

  * Automation rules: `list_automation_rules`, `create_automation_rule`,
    `update_automation_rule`, `delete_automation_rule`
  * Webhooks: `list_webhooks`, `create_webhook`, `delete_webhook`
  * Business hours: `get_working_hours`, `set_working_hours`
  * RSS autoposts and plugs: `list_autoposts`, `set_autopost_active`,
    `list_plugs`, `set_plug_active`
  * Help Center: `list_help_centers`, `list_articles`, `create_article`,
    `update_article`
  * Contacts: `merge_contacts`, `set_contact_blocked`

Publishing also has `refresh_publication_metrics`, `list_publishing_networks`,
`list_signatures` and `list_publication_sets`. Instagram (posts, comments,
products) has its own module.

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

```bash
python -m app.mcp http --host 0.0.0.0 --port 8765
#   → URL: http://<host>:8765/mcp
```

Agents connect with a Bearer token in the `Authorization` header
(same token they'd set in `MCP_BEARER_TOKEN` for stdio). Put a TLS
terminator (Caddy / nginx / Cloudflare) in front of the HTTP transport
in production — fastmcp's HTTP server doesn't do TLS or rate-limiting
itself. See [`INTEGRATIONS.md`](../../INTEGRATIONS.md#1-mcp-server)
for the external-agent contract (auth, scope hierarchy, recommended
client setup).

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
