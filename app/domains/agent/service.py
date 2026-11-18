"""The agent chat turn: an OpenAI model with the MCP tools, as the user.

A turn sends the chat history to the model and runs the tools it asks for
until it answers in text. Read tools run right away. A tool that writes
waits as a ``pending`` row until the user confirms it
(:func:`confirm_action`) or rejects it (:func:`reject_action`). Writes that
stay in the database (``TRIAL_TOOLS``) are first tried inside a savepoint
that is rolled back, so an invalid proposal goes back to the model instead
of to the user; anything that messages a customer, calls Meta or notifies
the panel is never run before the user confirms it.

The tools are the MCP server's own (same descriptions, schemas and scope
checks), run in-process as the chatting user, in their account, seeing what
their role sees in the panel (``MCPContext.user_scoped``): an administrator
the whole account, an agent the conversations of their inboxes. Tools the
panel keeps to administrators (``requires(..., panel_admin=True)``) are not
offered to agents.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any, NamedTuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastmcp import FastMCP
from sqlalchemy import or_, update
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import llm
from app.core.config import get_settings
from app.core.deps import AccountContext
from app.core.errors import ChatwootHTTPException
from app.core.i18n import user_locale
from app.domains.agent.models import (
    AGENT_ROLE_ASSISTANT,
    AGENT_ROLE_TOOL,
    AGENT_ROLE_USER,
    TOOL_STATUS_DONE,
    TOOL_STATUS_ERROR,
    TOOL_STATUS_INVALID,
    TOOL_STATUS_PENDING,
    TOOL_STATUS_REJECTED,
    AgentMessage,
    AgentThread,
)
from app.domains.usage.ai import ai_usage
from app.mcp.context import MCPContext, bind_mcp_context, reset_mcp_context
from app.mcp.permissions import permissions_of

log = logging.getLogger(__name__)

# The proposals with a card of their own (presenters), and the only writes
# whose whole effect stays in the database: they are tried in a savepoint
# and rolled back before reaching the user. Every other write is proposed
# as is and runs only once confirmed.
PUBLICATION_TOOLS: frozenset[str] = frozenset({"create_publication", "cancel_publication"})
TRIAL_TOOLS: frozenset[str] = PUBLICATION_TOOLS

MAX_CONTENT_LENGTH = 4000
# Model calls per turn; the last one has to answer in text.
MAX_MODEL_CALLS = 8
# Messages of context sent to the model.
HISTORY_LIMIT = 40
# A long tool result is cut for the model (the publications of a busy month).
TOOL_RESULT_LIMIT = 12_000
# How long a turn may hold its chat before another request can take it over.
BUSY_TIMEOUT = timedelta(minutes=3)
TITLE_LENGTH = 60
# Date arguments of the tools (see :func:`_localize_dates`).
_DATE_ARGUMENTS: tuple[str, ...] = (
    "scheduled_for",
    "scheduled_at",
    "from",
    "to",
    "starts_at",
    "ends_at",
    "due_at",
)

_WEEKDAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")

# The language the user has the dashboard in, named for the prompt.
_LANGUAGE_NAMES = {
    "es": "español",
    "en": "inglés",
    "pt": "portugués",
    "fr": "francés",
    "de": "alemán",
    "ja": "japonés",
    "ko": "coreano",
}

class _ToolCatalog(NamedTuple):
    names: tuple[str, ...]  # sorted
    reads: frozenset[str]
    admin_only: frozenset[str]


_server: FastMCP | None = None
_catalog: _ToolCatalog | None = None


def _mcp_server() -> FastMCP:
    # Built once: the tools are plain functions; per-call state lives in
    # the context bound around each run.
    global _server
    if _server is None:
        from app.mcp.server import build_server

        _server = build_server()
    return _server


def agent_enabled() -> bool:
    return bool(get_settings().openai_api_key)


async def _tool_catalog() -> _ToolCatalog:
    """The MCP tools by what each one declared (``requires``). One that
    declared nothing counts as a write for administrators only."""
    global _catalog
    if _catalog is None:
        names: list[str] = []
        reads: set[str] = set()
        admin_only: set[str] = set()
        for tool in await _mcp_server().list_tools(run_middleware=False):
            names.append(tool.name)
            declared = permissions_of(getattr(tool, "fn", None))
            if declared is not None and declared.reads:
                reads.add(tool.name)
            if declared is None or declared.scope == "admin" or declared.panel_admin:
                admin_only.add(tool.name)
        _catalog = _ToolCatalog(tuple(sorted(names)), frozenset(reads), frozenset(admin_only))
    return _catalog


async def allowed_tools(ctx: AccountContext) -> tuple[str, ...]:
    """What the user's role may use, sorted (a stable prefix for the
    model's prompt cache)."""
    catalog = await _tool_catalog()
    if ctx.is_administrator:
        return catalog.names
    return tuple(name for name in catalog.names if name not in catalog.admin_only)


async def is_read_tool(name: str) -> bool:
    return name in (await _tool_catalog()).reads


def _unavailable() -> ChatwootHTTPException:
    return ChatwootHTTPException(
        status_code=503,
        detail={
            "message": (
                "El agente no está configurado: falta la clave de OpenAI en "
                "Ajustes → Instalación."
            )
        },
    )


def _unprocessable(message: str) -> ChatwootHTTPException:
    return ChatwootHTTPException(status_code=422, detail={"message": message})


def _not_pending() -> ChatwootHTTPException:
    return ChatwootHTTPException(
        status_code=409, detail={"message": "Esa acción ya no está pendiente."}
    )


def _clean_content(content: str) -> str:
    text = content.strip()
    if not text:
        raise _unprocessable("Escribí un mensaje.")
    if len(text) > MAX_CONTENT_LENGTH:
        raise _unprocessable(
            f"El mensaje no puede pasar de {MAX_CONTENT_LENGTH} caracteres."
        )
    return text


def _zone_name(timezone: str | None) -> str:
    if not timezone:
        return "UTC"
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise _unprocessable("La zona horaria no es válida.") from exc
    return timezone


def _title(text: str) -> str:
    line = " ".join(text.split())
    return line if len(line) <= TITLE_LENGTH else f"{line[: TITLE_LENGTH - 1]}…"


# ---------------------------------------------------------------------------
# Threads
# ---------------------------------------------------------------------------
async def list_threads(session: AsyncSession, ctx: AccountContext) -> list[AgentThread]:
    return list(
        (
            await session.exec(
                select(AgentThread)
                .where(
                    AgentThread.account_id == ctx.account.id,
                    AgentThread.user_id == ctx.user.id,
                )
                .order_by(AgentThread.updated_at.desc(), AgentThread.id.desc())  # type: ignore[attr-defined, union-attr]
            )
        ).all()
    )


async def get_thread(
    session: AsyncSession, ctx: AccountContext, thread_id: int
) -> AgentThread:
    """The user's own chat, or 404 (another user's chat does not exist)."""
    thread = (
        await session.exec(
            select(AgentThread).where(
                AgentThread.id == thread_id,
                AgentThread.account_id == ctx.account.id,
                AgentThread.user_id == ctx.user.id,
            )
        )
    ).first()
    if thread is None:
        raise ChatwootHTTPException(
            status_code=404, detail={"message": "No se encontró el chat."}
        )
    return thread


async def thread_messages(session: AsyncSession, thread_id: int) -> list[AgentMessage]:
    return list(
        (
            await session.exec(
                select(AgentMessage)
                .where(AgentMessage.thread_id == thread_id)
                .order_by(AgentMessage.id)  # type: ignore[arg-type]
            )
        ).all()
    )


async def pending_thread_ids(session: AsyncSession, thread_ids: list[int]) -> set[int]:
    if not thread_ids:
        return set()
    rows = (
        await session.exec(
            select(AgentMessage.thread_id).where(
                AgentMessage.thread_id.in_(thread_ids),  # type: ignore[attr-defined]
                AgentMessage.status == TOOL_STATUS_PENDING,
            )
        )
    ).all()
    return set(rows)


async def pending_row(session: AsyncSession, thread_id: int) -> AgentMessage | None:
    return (
        await session.exec(
            select(AgentMessage).where(
                AgentMessage.thread_id == thread_id,
                AgentMessage.status == TOOL_STATUS_PENDING,
            )
        )
    ).first()


async def delete_thread(session: AsyncSession, thread: AgentThread) -> None:
    await session.delete(thread)
    await session.flush()


# ---------------------------------------------------------------------------
# Turns
# ---------------------------------------------------------------------------
async def start_thread(
    session: AsyncSession, ctx: AccountContext, *, content: str, timezone: str | None
) -> AgentThread:
    """A new chat with its first message, answered."""
    if not agent_enabled():
        raise _unavailable()
    text = _clean_content(content)
    thread = AgentThread(
        account_id=ctx.account.id,  # type: ignore[arg-type]
        user_id=ctx.user.id,  # type: ignore[arg-type]
        title=_title(text),
        timezone=_zone_name(timezone),
        running_since=datetime.now(UTC),
    )
    session.add(thread)
    await session.flush()
    session.add(AgentMessage(thread_id=thread.id, role=AGENT_ROLE_USER, content=text))  # type: ignore[arg-type]
    await session.commit()
    try:
        await _run_model(session, ctx, thread)
    except ChatwootHTTPException as exc:
        # The chat and its message are saved: say which one, so the client
        # can open it even though the model did not answer.
        if isinstance(exc.detail, dict):
            exc.detail["thread_id"] = thread.id
        raise
    finally:
        await _release(session, thread)
    return thread


async def send_message(
    session: AsyncSession,
    ctx: AccountContext,
    thread: AgentThread,
    *,
    content: str,
    timezone: str | None,
) -> None:
    """The user's next message, answered. A proposal still waiting for
    confirmation is dropped: the user answered it with words instead."""
    if not agent_enabled():
        raise _unavailable()
    text = _clean_content(content)
    zone = _zone_name(timezone)
    await _claim(session, thread)
    try:
        pending = await pending_row(session, thread.id)  # type: ignore[arg-type]
        if pending is not None:
            _resolve_rejected(
                pending,
                "El usuario no lo confirmó y escribió un mensaje nuevo: no se hizo.",
            )
            session.add(pending)
        thread.timezone = zone
        session.add(thread)
        session.add(AgentMessage(thread_id=thread.id, role=AGENT_ROLE_USER, content=text))  # type: ignore[arg-type]
        await session.commit()
        await _run_model(session, ctx, thread)
    finally:
        await _release(session, thread)


async def confirm_action(
    session: AsyncSession, ctx: AccountContext, thread: AgentThread, action_id: str
) -> None:
    """Run the proposal the user confirmed, then let the agent follow up."""
    if not agent_enabled():
        raise _unavailable()
    await _claim(session, thread)
    try:
        row = await pending_row(session, thread.id)  # type: ignore[arg-type]
        if row is None or row.tool_call_id != action_id:
            raise _not_pending()
        ok, result = await _run_tool(
            session, ctx, row.tool_name or "", row.tool_arguments or {}, keep=True
        )
        row.status = TOOL_STATUS_DONE if ok else TOOL_STATUS_ERROR
        row.content = _dump(result)
        session.add(row)
        await session.commit()
        await _run_model(session, ctx, thread)
    finally:
        await _release(session, thread)


async def reject_action(
    session: AsyncSession, ctx: AccountContext, thread: AgentThread, action_id: str
) -> None:
    """Drop the proposal. The agent reads it on the user's next message."""
    await _claim(session, thread)
    try:
        row = await pending_row(session, thread.id)  # type: ignore[arg-type]
        if row is None or row.tool_call_id != action_id:
            raise _not_pending()
        _resolve_rejected(row, "El usuario no lo confirmó: no se hizo.")
        session.add(row)
        await session.commit()
    finally:
        await _release(session, thread)


def _resolve_rejected(row: AgentMessage, note: str) -> None:
    row.status = TOOL_STATUS_REJECTED
    row.content = _dump({"rejected": True, "message": note})


async def _claim(session: AsyncSession, thread: AgentThread) -> None:
    """Take the chat for this turn, or 409 if another turn holds it."""
    now = datetime.now(UTC)
    claimed = await session.exec(  # type: ignore[call-overload]
        update(AgentThread)
        .where(
            AgentThread.id == thread.id,  # type: ignore[arg-type]
            or_(
                AgentThread.running_since.is_(None),  # type: ignore[union-attr]
                AgentThread.running_since < now - BUSY_TIMEOUT,  # type: ignore[operator]
            ),
        )
        .values(running_since=now)
    )
    if claimed.rowcount == 0:
        raise ChatwootHTTPException(
            status_code=409,
            detail={"message": "El agente todavía está respondiendo en este chat."},
        )
    await session.commit()
    await session.refresh(thread)


async def _release(session: AsyncSession, thread: AgentThread) -> None:
    try:
        thread.running_since = None
        session.add(thread)
        await session.commit()
        # ``updated_at`` is set by the database on update.
        await session.refresh(thread)
    except Exception:
        log.exception("agent: could not release thread %s", thread.id)


async def _run_model(
    session: AsyncSession, ctx: AccountContext, thread: AgentThread
) -> None:
    """Call the model until it answers in text or proposes a write."""
    names = await allowed_tools(ctx)
    tools = await _tool_specs(names)
    for step in range(MAX_MODEL_CALLS):
        rows = await _history(session, thread.id)  # type: ignore[arg-type]
        messages = [{"role": "system", "content": _system_prompt(ctx, thread)}]
        messages += [m for m in (_as_openai(r) for r in rows) if m is not None]
        try:
            with ai_usage(session, ctx.account.id, "agent"):
                reply = await llm.chat_completion(
                    messages=messages,
                    tools=tools,
                    tool_choice="none" if step == MAX_MODEL_CALLS - 1 else None,
                )
        except llm.LlmError as exc:
            log.warning("agent: thread %s model call failed: %s", thread.id, exc)
            raise ChatwootHTTPException(
                status_code=502,
                detail={"message": "El agente no respondió. Probá de nuevo en un momento."},
            ) from exc
        calls = [c for c in reply.get("tool_calls") or [] if isinstance(c, dict)]
        session.add(
            AgentMessage(
                thread_id=thread.id,  # type: ignore[arg-type]
                role=AGENT_ROLE_ASSISTANT,
                content=reply.get("content") or "",
                tool_calls=calls or None,
            )
        )
        proposed = False
        for call in calls:
            proposed = await _handle_call(session, ctx, thread, call, names, proposed)
        await session.commit()
        if not calls or proposed:
            return


async def _handle_call(
    session: AsyncSession,
    ctx: AccountContext,
    thread: AgentThread,
    call: dict[str, Any],
    names: tuple[str, ...],
    proposed: bool,
) -> bool:
    """Answer one tool call with a tool row. True once a write is waiting
    for the user (one per turn: the rest of the turn waits for it)."""
    function = call.get("function") or {}
    name = str(function.get("name") or "")
    row = AgentMessage(
        thread_id=thread.id,  # type: ignore[arg-type]
        role=AGENT_ROLE_TOOL,
        tool_call_id=str(call.get("id") or ""),
        tool_name=name,
    )
    session.add(row)
    try:
        arguments = json.loads(function.get("arguments") or "{}")
    except ValueError:
        arguments = None
    if not isinstance(arguments, dict):
        row.status = TOOL_STATUS_ERROR
        row.content = _dump({"error": "Los argumentos no son un objeto JSON válido."})
        return proposed
    arguments = _localize_dates(arguments, thread.timezone)
    row.tool_arguments = arguments
    if name not in names:
        row.status = TOOL_STATUS_ERROR
        row.content = _dump({"error": f"La herramienta {name} no está disponible."})
        return proposed
    if await is_read_tool(name):
        ok, result = await _run_tool(session, ctx, name, arguments, keep=True)
        row.status = TOOL_STATUS_DONE if ok else TOOL_STATUS_ERROR
        row.content = _dump(result)
        return proposed
    if proposed:
        row.status = TOOL_STATUS_ERROR
        row.content = _dump({"error": "Proponé una sola acción por vez."})
        return proposed
    if name in TRIAL_TOOLS:
        ok, result = await _run_tool(session, ctx, name, arguments, keep=False)
        if not ok:
            row.status = TOOL_STATUS_INVALID
            row.content = _dump(result)
            return proposed
    row.status = TOOL_STATUS_PENDING
    return True


def _localize_dates(arguments: dict[str, Any], zone_name: str | None) -> dict[str, Any]:
    """A date argument without an offset means the user's local time; the
    service would read it as UTC and post hours off."""
    zone = ZoneInfo(zone_name or "UTC")
    localized = dict(arguments)
    for key in _DATE_ARGUMENTS:
        raw = localized.get(key)
        if not isinstance(raw, str):
            continue
        try:
            parsed = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
        except ValueError:
            continue
        if parsed.tzinfo is None:
            localized[key] = parsed.replace(tzinfo=zone).isoformat()
    return localized


async def _tool_specs(names: tuple[str, ...]) -> list[dict[str, Any]]:
    """The tools as OpenAI functions, straight from the MCP server."""
    specs: list[dict[str, Any]] = []
    for name in names:
        tool = await _mcp_server().get_tool(name)
        if tool is None:
            continue
        specs.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.parameters,
                },
            }
        )
    return specs


async def _run_tool(
    session: AsyncSession,
    ctx: AccountContext,
    name: str,
    arguments: dict[str, Any],
    *,
    keep: bool,
) -> tuple[bool, dict[str, Any]]:
    """Run an MCP tool as the chatting user, inside a savepoint that is kept
    only when ``keep`` (a trial run of a proposal leaves nothing behind).
    Returns ``(ok, result)``; a failure is ``{"error": ...}`` for the model."""
    tool = await _mcp_server().get_tool(name)
    if tool is None or name not in await allowed_tools(ctx):
        return False, {"error": f"La herramienta {name} no está disponible."}
    binding = bind_mcp_context(
        MCPContext(
            user=ctx.user,
            account=ctx.account,
            # The role decides (allowed_tools and the tools' own visibility
            # checks); the scope only has to let those tools run.
            scope="admin" if ctx.is_administrator else "write",
            session=session,
            user_scoped=True,
        )
    )
    savepoint = await session.begin_nested()
    try:
        result = await tool.run(arguments)
    except Exception as exc:  # noqa: BLE001 — the model reads it and adjusts
        if savepoint.is_active:
            await savepoint.rollback()
        log.info("agent: tool %s failed: %s", name, exc)
        return False, {"error": _error_text(exc)}
    finally:
        reset_mcp_context(binding)
    # Some services commit on their own (sending an Instagram attachment,
    # retrying a publication): the savepoint is gone and what they did
    # already happened, so there is nothing left to keep or undo.
    if savepoint.is_active:
        if keep:
            await savepoint.commit()
        else:
            await savepoint.rollback()
    elif not keep:
        log.error("agent: trial of %s committed on its own and could not be undone", name)
    payload = result.structured_content
    if not isinstance(payload, dict):
        text = "\n".join(getattr(part, "text", "") for part in result.content)
        payload = {"result": text}
    return True, payload


def _error_text(exc: Exception) -> str:
    if isinstance(exc, ChatwootHTTPException) and isinstance(exc.detail, dict):
        message = str(exc.detail.get("message") or exc.detail.get("error") or exc.detail)
        errors = exc.detail.get("errors")
        if errors:
            message = f"{message}: {'; '.join(str(e) for e in errors)}"
        return message[:500]
    return (str(exc) or type(exc).__name__)[:500]


def _dump(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, ensure_ascii=False, default=str)
    if len(text) > TOOL_RESULT_LIMIT:
        text = f"{text[:TOOL_RESULT_LIMIT]}… (resultado recortado)"
    return text


async def _history(session: AsyncSession, thread_id: int) -> list[AgentMessage]:
    """The last messages, starting at a user message: a cut through a tool
    exchange would leave results without the call that asked for them."""
    rows = list(
        (
            await session.exec(
                select(AgentMessage)
                .where(AgentMessage.thread_id == thread_id)
                .order_by(AgentMessage.id.desc())  # type: ignore[union-attr]
                .limit(HISTORY_LIMIT)
            )
        ).all()
    )
    rows.reverse()
    while rows and rows[0].role != AGENT_ROLE_USER:
        rows.pop(0)
    return rows


def _as_openai(row: AgentMessage) -> dict[str, Any] | None:
    if row.role == AGENT_ROLE_USER:
        return {"role": "user", "content": row.content or ""}
    if row.role == AGENT_ROLE_ASSISTANT:
        message: dict[str, Any] = {"role": "assistant", "content": row.content or ""}
        if row.tool_calls:
            message["tool_calls"] = row.tool_calls
        return message
    if row.status == TOOL_STATUS_PENDING:
        return None
    return {"role": "tool", "tool_call_id": row.tool_call_id, "content": row.content or ""}


def _system_prompt(ctx: AccountContext, thread: AgentThread) -> str:
    zone = ZoneInfo(thread.timezone or "UTC")
    now = datetime.now(zone)
    offset = now.strftime("%z")
    role = "administrador" if ctx.is_administrator else "agente"
    lines = [
        f'Sos el agente de AloStudio de la cuenta "{ctx.account.name}". '
        f"Hablás con {ctx.user.name or 'un usuario de la cuenta'}, que es "
        f"{role} de la cuenta.",
        f"Ahora es {_WEEKDAYS[now.weekday()]} {now:%Y-%m-%d %H:%M} en la zona "
        f"{zone.key} (UTC{offset[:3]}:{offset[3:]}).",
        "Ayudás con lo que se hace en AloStudio: buscar y responder "
        "conversaciones, contactos, CRM, Agenda, productos, publicaciones y "
        "reportes, con las herramientas que tenés.",
        "",
        "Reglas:",
        "- Respondé en el idioma en que te escribe el usuario, breve y claro, "
        "en texto plano: párrafos cortos y listas con guiones. Sin markdown "
        "(nada de **, #, tablas ni enlaces entre corchetes). "
        f"Tiene la app en {_LANGUAGE_NAMES[user_locale(ctx.user)]}: si no se "
        "entiende en qué idioma escribe, usá ese.",
        "- Usá solo ids que te devolvieron las herramientas (list_..., "
        "search_..., show_...). Nunca inventes ids. Si hay varios candidatos, "
        "preguntá cuál.",
        "- Lo que cambia algo (mandar un mensaje, asignar, agendar, crear o "
        "borrar) lo confirma el usuario en una tarjeta que le muestra la app. "
        "Antes de llamar a esa herramienta explicá en una línea qué vas a "
        "hacer; no pidas confirmación en el texto. Si la rechaza o pide "
        "cambios, armá otra propuesta.",
        "- Un mensaje a un cliente lo lee el cliente: escribilo como lo "
        "escribiría la persona del equipo.",
        "- Las fechas que mandes a las herramientas van en ISO 8601 con la "
        "zona del usuario. Para publicar: sin scheduled_for la publicación "
        "sale en los próximos minutos.",
        "- Si una herramienta devuelve un error, corregí y probá de nuevo, o "
        "explicale al usuario qué pasa.",
        "- Para publicar, consultá los canales con list_publication_channels "
        "(uno con status \"reconnect\" no puede publicar) y las imágenes o "
        "videos con list_media; pasalos como {\"media_id\": id}. No podés "
        "generar imágenes ni videos.",
    ]
    if ctx.is_administrator:
        lines.append(
            "- Es administrador: ve toda la cuenta y puede cambiar la "
            "configuración que exponen las herramientas."
        )
    else:
        lines.append(
            "- Es agente: ve y toca solo las conversaciones de sus bandejas. "
            "La configuración de la cuenta (productos, campañas, etiquetas "
            "nuevas, Instagram, publicaciones, automatizaciones) la cambia un "
            "administrador: si lo pide, decíselo."
        )
    return "\n".join(lines)


__all__ = [
    "MAX_CONTENT_LENGTH",
    "PUBLICATION_TOOLS",
    "TRIAL_TOOLS",
    "agent_enabled",
    "allowed_tools",
    "confirm_action",
    "delete_thread",
    "get_thread",
    "is_read_tool",
    "list_threads",
    "pending_row",
    "pending_thread_ids",
    "reject_action",
    "send_message",
    "start_thread",
    "thread_messages",
]
