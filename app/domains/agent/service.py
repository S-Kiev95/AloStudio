"""The agent chat turn: an OpenAI model with the publishing MCP tools.

A turn sends the chat history to the model and runs the tools it asks for
until it answers in text. Read tools run right away. A tool that writes
(create or cancel a publication) is first tried inside a savepoint that is
rolled back, so an invalid proposal goes back to the model instead of to
the user, and then waits as a ``pending`` row until the user confirms it
(:func:`confirm_action`) or rejects it (:func:`reject_action`).

The tools are the MCP server's own (same descriptions, schemas and scope
checks), run in-process as the chatting user, in their account, with a
scope taken from their role: administrators write, agents only read, like
the publications REST API.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastmcp import FastMCP
from sqlalchemy import or_, update
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import llm
from app.core.config import get_settings
from app.core.deps import AccountContext
from app.core.errors import ChatwootHTTPException
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
from app.mcp.context import MCPContext, bind_mcp_context, reset_mcp_context

log = logging.getLogger(__name__)

READ_TOOLS: tuple[str, ...] = (
    "list_publication_channels",
    "list_media",
    "list_publications",
    "get_publishing_analytics",
)
# Never run without the user's confirmation.
WRITE_TOOLS: tuple[str, ...] = ("create_publication", "cancel_publication")

MAX_CONTENT_LENGTH = 4000
# Model calls per turn; the last one has to answer in text.
MAX_MODEL_CALLS = 6
# Messages of context sent to the model.
HISTORY_LIMIT = 40
# A long tool result is cut for the model (the publications of a busy month).
TOOL_RESULT_LIMIT = 12_000
# How long a turn may hold its chat before another request can take it over.
BUSY_TIMEOUT = timedelta(minutes=3)
TITLE_LENGTH = 60
# Date arguments of the publishing tools (see :func:`_localize_dates`).
_DATE_ARGUMENTS: tuple[str, ...] = ("scheduled_for", "from", "to")

_WEEKDAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")

_server: FastMCP | None = None


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


def allowed_tools(ctx: AccountContext) -> tuple[str, ...]:
    return READ_TOOLS + WRITE_TOOLS if ctx.is_administrator else READ_TOOLS


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
    names = allowed_tools(ctx)
    tools = await _tool_specs(names)
    for step in range(MAX_MODEL_CALLS):
        rows = await _history(session, thread.id)  # type: ignore[arg-type]
        messages = [{"role": "system", "content": _system_prompt(ctx, thread)}]
        messages += [m for m in (_as_openai(r) for r in rows) if m is not None]
        try:
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
    if name not in WRITE_TOOLS:
        ok, result = await _run_tool(session, ctx, name, arguments, keep=True)
        row.status = TOOL_STATUS_DONE if ok else TOOL_STATUS_ERROR
        row.content = _dump(result)
        return proposed
    if proposed:
        row.status = TOOL_STATUS_ERROR
        row.content = _dump({"error": "Proponé una sola acción por vez."})
        return proposed
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
    if tool is None or name not in allowed_tools(ctx):
        return False, {"error": f"La herramienta {name} no está disponible."}
    binding = bind_mcp_context(
        MCPContext(
            user=ctx.user,
            account=ctx.account,
            scope="write" if ctx.is_administrator else "read",
            session=session,
        )
    )
    savepoint = await session.begin_nested()
    try:
        result = await tool.run(arguments)
    except Exception as exc:  # noqa: BLE001 — the model reads it and adjusts
        await savepoint.rollback()
        log.info("agent: tool %s failed: %s", name, exc)
        return False, {"error": _error_text(exc)}
    finally:
        reset_mcp_context(binding)
    if keep:
        await savepoint.commit()
    else:
        await savepoint.rollback()
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
    lines = [
        f'Sos el agente de AloStudio de la cuenta "{ctx.account.name}". '
        f"Hablás con {ctx.user.name or 'un usuario de la cuenta'}.",
        f"Ahora es {_WEEKDAYS[now.weekday()]} {now:%Y-%m-%d %H:%M} en la zona "
        f"{zone.key} (UTC{offset[:3]}:{offset[3:]}).",
        "Ayudás a armar y programar publicaciones en las redes conectadas de la "
        "cuenta, a revisar qué hay programado y a contar cómo les fue a las "
        "publicaciones.",
        "",
        "Reglas:",
        "- Respondé en el idioma del usuario, breve y claro, en texto plano: "
        "párrafos cortos y listas con guiones. Sin markdown (nada de **, #, "
        "tablas ni enlaces entre corchetes).",
        "- Antes de crear una publicación consultá los canales con "
        "list_publication_channels y usá solo sus id. Nunca inventes ids. Un "
        'canal con status "reconnect" no puede publicar: avisale al usuario.',
        "- Para usar imágenes o videos buscalos con list_media y pasalos como "
        '{"media_id": id}. No podés generar imágenes ni videos.',
        "- Si falta un dato imprescindible (en qué canales, cuándo), "
        'preguntalo. "Todos mis canales" son todos los que pueden publicar.',
        "- Las fechas que mandes a las herramientas van en ISO 8601 con la "
        "zona del usuario. Sin scheduled_for la publicación sale en los "
        "próximos minutos: dejalo vacío solo si el usuario pide publicar ya.",
        "- Si una herramienta devuelve un error (por ejemplo un texto más "
        "largo de lo que acepta una red), corregí la propuesta y probá de "
        "nuevo, o explicale al usuario qué pasa.",
        "- No tenés acceso a la bandeja de mensajes ni a los contactos.",
    ]
    if ctx.is_administrator:
        lines.append(
            "- Crear y borrar publicaciones lo confirma el usuario en una "
            "tarjeta que le muestra la app. No pidas confirmación en el "
            "texto: llamá a la herramienta con la propuesta completa y la "
            "app se la muestra. Si la rechaza o pide cambios, armá otra."
        )
    else:
        lines.append(
            "- Este usuario no es administrador: podés consultar "
            "publicaciones y estadísticas, pero no crear ni borrar. Si lo "
            "pide, decile que lo tiene que hacer un administrador."
        )
    return "\n".join(lines)


__all__ = [
    "MAX_CONTENT_LENGTH",
    "READ_TOOLS",
    "WRITE_TOOLS",
    "agent_enabled",
    "allowed_tools",
    "confirm_action",
    "delete_thread",
    "get_thread",
    "list_threads",
    "pending_row",
    "pending_thread_ids",
    "reject_action",
    "send_message",
    "start_thread",
    "thread_messages",
]
