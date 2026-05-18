# Feature branch — MCP server

**Branch:** `feat/mcp-server` (off `main` at the close of Phase 10)

**Goal:** Expose this backend's read + write operations as MCP tools
so AI agents (Langchain / Langgraph / OpenAI Assistants / Claude
Desktop / etc.) can interact with conversations without embedding an
orchestrator in this process.

**Why MCP instead of in-process Langgraph:**
  * Zero AI weight on the core backend (no LLM clients, no prompts,
    no vector stores in the request path).
  * Tech-stack freedom per agent — each external app picks its own
    framework as long as it speaks MCP.
  * Independent deploys — bumping the agent's prompt doesn't redeploy
    the Chatwoot-mirror.
  * Multi-agent compositions for free.

**Key reference:**
  * `https://modelcontextprotocol.io/` for the protocol contract.
  * `fastmcp` 3.x as the Python implementation (added to deps).

---

## Architecture

```
┌─────────────────────────────────────┐
│ AloStudio backend                   │
│  ├─ FastAPI app (Chatwoot mirror)   │  unchanged
│  ├─ AgentBot push (HMAC webhooks)   │  unchanged
│  └─ MCP server (fastmcp) ──────────┐│  ← new
└────────────────────────────────────┼┘
                                     ▼
                          ┌──────────────────┐
                          │ MCP transport    │
                          │ (stdio │ http)   │
                          └──────────────────┘
                                     ▲
                  ┌──────────────────┼──────────────────┐
                  │                  │                  │
              ┌───────┐         ┌────────┐         ┌────────┐
              │ Auto- │         │ FAQ    │         │ Claude │
              │ reply │         │ classif│         │ Desktop│
              └───────┘         └────────┘         └────────┘
```

Auth: API tokens reusing the existing polymorphic ``access_tokens``
table (Phase 1). Each token grants scope to one Account + a permission
mask (read / write / admin).

State sharing: per-conversation ``ai_mode`` flag lives in
``conversation.additional_attributes["ai_mode"]`` (JSONB — no
migration needed). External agents read/write it via dedicated MCP
tools.

---

## Scope decisions

**In scope:**
  * FastMCP scaffold + API-key auth (read from `access_tokens`).
  * Conversation tools: list / show / resolve / reopen / assign-agent
    / assign-team / change-priority / change-status / add-label /
    remove-label / set-ai-mode.
  * Message tools: list / send-message / add-private-note / show.
  * Contact tools: list / show / search / set-custom-attribute.
  * Label tools: list (read-only, account-scoped).
  * Report tools: read-only `/reports/summary` + live counters.
  * Per-token permission scope (`read`, `write`, `admin`).
  * Tests with the MCP test harness.

**Out of scope (logged):**
  * Mutation tools for portals/articles/campaigns/macros/automation —
    those are admin-config concerns; agents shouldn't be editing them
    unsupervised.
  * Streaming tool results (FastMCP supports it but no consumer needs
    it in v1).
  * Embeddings / vector search tools — defer to a `feat/ai-rag` branch
    when there's an actual use case.

---

## Milestones

### M.1 — FastMCP scaffold + API-key auth

**Tasks:**
- [x] `app/mcp/__init__.py` + `app/mcp/server.py` — FastMCP instance
      + bootstrap.
- [x] `app/mcp/auth.py` — API-key validator that reads
      ``access_tokens`` + verifies the owner is an `AccountUser` of
      the account in scope. Returns `MCPContext` with account_id +
      user_id + permission scope.
- [x] `app/mcp/transport.py` — selectable transport (stdio for
      Claude Desktop, HTTP for remote agents).
- [x] First end-to-end "hello" tool to verify the wire.
- [x] Tests: auth happy path + bad token + token from another
      account.

### M.2 — Conversation tools

**Tasks:**
- [x] `list_conversations(status?, assignee_id?, label?, page?)`
- [x] `show_conversation(conversation_id)` — returns the conv shape
      + the last N messages (default 10).
- [x] `resolve_conversation(conversation_id)`
- [x] `reopen_conversation(conversation_id)`
- [x] `assign_agent(conversation_id, agent_id | "self" | null)`
- [x] `assign_team(conversation_id, team_id | null)`
- [x] `change_priority(conversation_id, priority)`
- [x] `change_status(conversation_id, status)`
- [x] `add_label(conversation_id, labels)` + `remove_label(...)`
- [x] `set_ai_mode(conversation_id, mode: "auto"|"manual")` —
      writes `additional_attributes["ai_mode"]`. The 'manual' value
      is the agent's way of asking for human takeover.
- [x] `get_ai_mode(conversation_id)` — read.
- [x] Tests per tool.

### M.3 — Message tools

**Tasks:**
- [x] `list_messages(conversation_id, before?, limit?)` —
      paginated, newest-first.
- [x] `send_message(conversation_id, content, private?=false)` —
      reuses `MessageBuilder`. With ``private=true``
      becomes a private note.
- [x] `add_private_note(conversation_id, content)` — sugar.
- [x] `show_message(message_id)` — read with full content_attributes.
- [x] Tests.

### M.4 — Contact tools

**Tasks:**
- [x] `list_contacts(query?, page?)` — server-side search.
- [x] `show_contact(contact_id)` — full contact + recent conversations.
- [x] `set_contact_custom_attribute(contact_id, key, value)` —
      writes the contact-side custom_attributes JSONB.
- [x] `set_conversation_custom_attribute(conversation_id, key, value)` —
      same for conversation-side.
- [x] Tests.

### M.5 — Labels + reports tools

**Tasks:**
- [x] `list_labels()` — account-scoped, ordered by title.
- [x] `get_account_summary(since?, until?)` — proxy to Phase 7.2
      summary report.
- [x] `get_live_metrics()` — proxy to Phase 7.4 live counters.
- [x] Tests.

### M.6 — Permission model

**Tasks:**
- [x] Add `scope` column to a new `mcp_tokens` table (separate from
      the polymorphic `access_tokens` — agents don't need user-level
      identity, they need account-level identity). Enum:
      `read` / `write` / `admin`.
- [x] Alembic migration.
- [x] Each tool declares its required permission (decorator);
      `MCPContext` short-circuits with a "permission denied" error
      when the token lacks it.
- [x] Tests: read-only token can't send messages, etc.

### M.7 — End-to-end tests + close branch

- [x] One full scenario: external agent connects, lists open
      conversations, sends a reply, resolves it.
- [x] README section explaining how to point Claude Desktop at the
      MCP server.
- [x] Mark feature done in a CHANGELOG entry on this branch.

---

## Commit style

`mcp.<n>: <area>: <short summary>` — one commit per milestone.
