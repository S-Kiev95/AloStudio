"""What AloStudio's AI can do for a customer (PLAN.agente-ia.md, 2b).

Every tool is bound to the conversation it answers: none takes an id, so a
customer can only reach the business's public knowledge and their own
contact. Reading (Help Center, products, free times) is always on. Writing
is off until an administrator allows it on the bot (``can_book``,
``can_update_crm``).

Shadow mode runs no write: the tool answers as if it had worked (so the
proposed reply reads right) and the action is listed with the suggestion,
for a person to do. Live, each write leaves a line in the conversation.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, or_
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import llm
from app.core.i18n import DEFAULT_LOCALE, t
from app.domains.ai_agent.gate import AiConfig
from app.domains.conversations.activities import create_activity_message
from app.domains.conversations.models import Conversation

log = logging.getLogger(__name__)

TOOL_HANDOFF = "hand_off_to_person"
TOOL_SEARCH = "search_help_center"
TOOL_PRODUCTS = "list_products"
TOOL_FREE_TIMES = "list_free_times"
TOOL_BOOK = "book_appointment"
TOOL_CONTACT = "save_contact_details"
TOOL_STAGE = "set_contact_stage"
TOOL_LABEL = "add_label"
TOOL_OPPORTUNITY = "create_opportunity"

RESULT_LIMIT = 6000
ARTICLE_TEXT_LIMIT = 1500
# Free times: how far ahead, how many at once, and the least notice.
BOOKING_DAYS = 14
FREE_TIMES_MAX = 8
BOOKING_NOTICE = timedelta(hours=1)

_ACTIVE_APPOINTMENT_STATUSES = ("scheduled", "confirmed")
# pg_advisory_xact_lock(key, account_id) for booking.
_BOOKING_LOCK = 72_011
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _spec(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


_TEXT = {"type": "string"}

_READ_SPECS = [
    _spec(
        TOOL_SEARCH,
        "Busca en el Centro de ayuda del negocio (preguntas frecuentes, políticas, "
        "horarios, precios publicados). Usala antes de responder sobre el negocio.",
        {"query": {"type": "string", "description": "Qué buscar."}},
        ["query"],
    ),
    _spec(
        TOOL_PRODUCTS,
        "Lista los productos y servicios activos del negocio, con precio. Con query "
        "filtra por nombre o descripción.",
        {"query": _TEXT},
        [],
    ),
]
_HANDOFF_SPEC = _spec(
    TOOL_HANDOFF,
    "Pasa la conversación a una persona del equipo. Usala cuando el cliente lo pide, "
    "cuando no encontrás la respuesta, para cerrar una venta o un trámite que no podés "
    "hacer, o si el cliente está molesto. Termina tu turno.",
    {
        "summary": {
            "type": "string",
            "description": "Para el equipo: quién es, qué necesita y qué ya se le dijo. Dos o tres líneas.",
        },
        "reply": {
            "type": "string",
            "description": "Para el cliente: avisale que lo atiende una persona. Opcional.",
        },
    },
    ["summary"],
)
_BOOKING_SPECS = [
    _spec(
        TOOL_FREE_TIMES,
        "Horarios libres para una cita, desde una fecha (por defecto hoy), en la hora "
        "local del negocio. Ofrecé solo estos.",
        {"from_date": {"type": "string", "description": "AAAA-MM-DD. Opcional."}},
        [],
    ),
    _spec(
        TOOL_BOOK,
        "Agenda una cita para este cliente en un horario libre. Confirmá antes con el "
        "cliente el día y la hora.",
        {
            "starts_at": {
                "type": "string",
                "description": "El inicio, tal como lo dio list_free_times.",
            },
            "product": {"type": "string", "description": "El producto o servicio, si aplica."},
        },
        ["starts_at"],
    ),
]
_CRM_SPECS = [
    _spec(
        TOOL_CONTACT,
        "Guarda el nombre o el email que el cliente te dio. Solo completa lo que falta.",
        {"name": _TEXT, "email": _TEXT},
        [],
    ),
    _spec(
        TOOL_STAGE,
        "Mueve al cliente a una etapa del ciclo de vida del negocio (por ejemplo, "
        "cuando está por comprar). Si no existe, te dice cuáles hay.",
        {"stage": {"type": "string", "description": "El nombre o la clave de la etapa."}},
        ["stage"],
    ),
    _spec(
        TOOL_LABEL,
        "Pone a la conversación una etiqueta que ya existe en la cuenta. Si no existe, "
        "te dice cuáles hay.",
        {"label": _TEXT},
        ["label"],
    ),
    _spec(
        TOOL_OPPORTUNITY,
        "Crea una oportunidad de venta en el CRM para este cliente, cuando muestra "
        "interés concreto en comprar.",
        {
            "title": {"type": "string", "description": "Qué quiere comprar, en pocas palabras."},
            "product": _TEXT,
            "value": {"type": "number", "description": "El monto, si se habló."},
        },
        ["title"],
    ),
]


def specs_for(config: AiConfig) -> list[dict[str, Any]]:
    """The tools this bot offers the model."""
    specs = [*_READ_SPECS, _HANDOFF_SPEC]
    if config.can_book:
        specs += _BOOKING_SPECS
    if config.can_update_crm:
        specs += _CRM_SPECS
    return specs


@dataclass
class ToolRun:
    """One run's context: the conversation and what this bot may do."""

    conversation: Conversation
    config: AiConfig
    live: bool
    # Writes done (live) or proposed (shadow), as lines for people.
    actions: list[str] = field(default_factory=list)


class _Refused(Exception):
    """Back to the model as an error it can explain or fix."""


def dump(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, ensure_ascii=False, default=str)
    return text if len(text) <= RESULT_LIMIT else f"{text[:RESULT_LIMIT]}…"


async def run_tool(
    session: AsyncSession, run: ToolRun, name: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Run one tool inside a savepoint: a failure goes back to the model and
    leaves nothing behind."""
    handler = _HANDLERS.get(name)
    offered = {s["function"]["name"] for s in specs_for(run.config)}
    if handler is None or name not in offered:
        return {"error": f"La herramienta {name} no existe."}
    savepoint = await session.begin_nested()
    try:
        result = await handler(session, run, arguments)
    except _Refused as exc:
        if savepoint.is_active:
            await savepoint.rollback()
        return {"error": str(exc)}
    except Exception as exc:  # noqa: BLE001 — the model reads it and adjusts
        if savepoint.is_active:
            await savepoint.rollback()
        log.info("ai_agent: tool %s failed: %s", name, exc)
        return {"error": "No se pudo hacer."}
    if savepoint.is_active:
        await savepoint.commit()
    return result


async def _act(session: AsyncSession, run: ToolRun, action: str) -> None:
    """Record a write: an activity line live, a proposal in shadow."""
    run.actions.append(action)
    if run.live:
        await create_activity_message(
            session,
            conversation=run.conversation,
            content=t(DEFAULT_LOCALE, "ai_agent.done", action=action),
        )


# ---------------------------------------------------------------------------
# Knowledge
# ---------------------------------------------------------------------------
async def _search_help_center(session: AsyncSession, run: ToolRun, args: dict[str, Any]) -> dict[str, Any]:
    from app.domains.portals.embeddings import vector_search
    from app.domains.portals.models import ARTICLE_STATUS_PUBLISHED, Article, Portal

    query = str(args.get("query") or "").strip()
    account_id = run.conversation.account_id
    if not query:
        return {"articles": []}
    portal_ids = list(
        (
            await session.exec(
                select(Portal.id).where(Portal.account_id == account_id, col(Portal.archived).is_(False))
            )
        ).all()
    )
    found: list[Article] = []
    try:
        # Billed as "help_center" (vector_search's own scope).
        for portal_id in portal_ids:
            found += await vector_search(session, portal_id=portal_id, query=query, limit=3)  # type: ignore[arg-type]
    except llm.LlmError as exc:
        log.info("ai_agent: help center embedding failed, plain search: %s", exc)
        found = []
    if not found and portal_ids:
        # Articles not indexed yet, or no embedding: plain text match.
        pattern = f"%{query}%"
        found = list(
            (
                await session.exec(
                    select(Article)
                    .where(
                        col(Article.portal_id).in_(portal_ids),
                        Article.status == ARTICLE_STATUS_PUBLISHED,
                        or_(col(Article.title).ilike(pattern), col(Article.content).ilike(pattern)),
                    )
                    .limit(3)
                )
            ).all()
        )
    return {
        "articles": [
            {"title": a.title, "content": (a.content or a.description or "")[:ARTICLE_TEXT_LIMIT]}
            for a in found[:5]
        ]
    }


async def _products(session: AsyncSession, run: ToolRun, args: dict[str, Any]) -> dict[str, Any]:
    from app.domains.products.models import Product

    query = str(args.get("query") or "").strip()
    stmt = select(Product).where(
        Product.account_id == run.conversation.account_id, col(Product.enabled).is_(True)
    )
    if query:
        pattern = f"%{query}%"
        stmt = stmt.where(or_(col(Product.name).ilike(pattern), col(Product.description).ilike(pattern)))
    rows = (await session.exec(stmt.order_by(col(Product.name)).limit(20))).all()
    return {
        "products": [
            {
                "name": p.name,
                "description": (p.description or "")[:300],
                "price": str(p.price) if p.price is not None else None,
                "currency": p.currency,
                "url": p.url,
            }
            for p in rows
        ]
    }


async def _product_named(session: AsyncSession, account_id: int, name: Any) -> Any:
    """An enabled product of the account by its name, or None."""
    from app.domains.products.models import Product

    if not isinstance(name, str) or not name.strip():
        return None
    product = (
        await session.exec(
            select(Product).where(
                Product.account_id == account_id,
                col(Product.enabled).is_(True),
                func.lower(Product.name) == name.strip().lower(),
            )
        )
    ).first()
    if product is None:
        raise _Refused(f"No hay un producto llamado {name}. Consultá list_products.")
    return product


# ---------------------------------------------------------------------------
# Agenda
# ---------------------------------------------------------------------------
def _zone(run: ToolRun) -> ZoneInfo:
    name = getattr(run.conversation.inbox, "timezone", None) or "UTC"
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


async def _free_slots(
    session: AsyncSession, run: ToolRun, start: datetime, *, days: int
) -> list[datetime]:
    """Starts of free slots: inside the inbox's hours, not overlapping an
    active appointment of the account, from ``start`` on."""
    from app.domains.appointments.models import Appointment
    from app.domains.working_hours.service import list_for_inbox, open_windows

    inbox = run.conversation.inbox
    if inbox is None or not inbox.working_hours_enabled:
        raise _Refused(
            "El negocio no cargó su horario para citas: pasá la conversación a una persona."
        )
    length = timedelta(minutes=run.config.slot_minutes)
    earliest = datetime.now(UTC) + BOOKING_NOTICE
    rows = await list_for_inbox(session, inbox_id=run.conversation.inbox_id)
    zone = _zone(run)
    windows = open_windows(rows=rows, timezone_name=zone.key, start=start, days=days)
    if not windows:
        return []
    busy = [
        (a.starts_at, a.ends_at or a.starts_at + length)
        for a in (
            await session.exec(
                select(Appointment).where(
                    Appointment.account_id == run.conversation.account_id,
                    col(Appointment.status).in_(_ACTIVE_APPOINTMENT_STATUSES),
                    col(Appointment.starts_at) < windows[-1][1],
                    col(Appointment.starts_at) >= windows[0][0] - timedelta(days=1),
                )
            )
        ).all()
    ]
    slots: list[datetime] = []
    for opens, closes in windows:
        slot = opens
        while slot + length <= closes:
            if slot >= max(start, earliest) and not any(
                b_start < slot + length and b_end > slot for b_start, b_end in busy
            ):
                slots.append(slot)
            slot += length
    return slots


async def _list_free_times(session: AsyncSession, run: ToolRun, args: dict[str, Any]) -> dict[str, Any]:
    zone = _zone(run)
    start = datetime.now(zone)
    raw = args.get("from_date")
    if isinstance(raw, str) and raw.strip():
        try:
            start = max(start, datetime.fromisoformat(raw.strip()[:10]).replace(tzinfo=zone))
        except ValueError as exc:
            raise _Refused("from_date tiene que ser AAAA-MM-DD.") from exc
    slots = await _free_slots(session, run, start, days=BOOKING_DAYS)
    return {
        "minutes": run.config.slot_minutes,
        "free_times": [s.astimezone(zone).isoformat() for s in slots[:FREE_TIMES_MAX]],
    }


async def _book(session: AsyncSession, run: ToolRun, args: dict[str, Any]) -> dict[str, Any]:
    from app.domains.appointments.models import Appointment
    from app.domains.appointments.service import create_appointment

    zone = _zone(run)
    try:
        starts = datetime.fromisoformat(str(args.get("starts_at") or "").strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise _Refused("starts_at no es una fecha válida.") from exc
    if starts.tzinfo is None:
        starts = starts.replace(tzinfo=zone)
    if starts > datetime.now(UTC) + timedelta(days=BOOKING_DAYS):
        raise _Refused(f"Solo se agenda hasta {BOOKING_DAYS} días adelante.")
    account_id = run.conversation.account_id
    # One booking at a time per account until the run commits: two chats
    # can't take the same time.
    await session.exec(select(func.pg_advisory_xact_lock(_BOOKING_LOCK, account_id)))
    upcoming = (
        await session.exec(
            select(Appointment.starts_at).where(
                Appointment.account_id == account_id,
                Appointment.contact_id == run.conversation.contact_id,
                col(Appointment.status).in_(_ACTIVE_APPOINTMENT_STATUSES),
                col(Appointment.starts_at) > datetime.now(UTC),
            )
        )
    ).first()
    if upcoming is not None:
        raise _Refused(
            f"Ya tiene una cita el {upcoming.astimezone(zone):%Y-%m-%d %H:%M}. "
            "Para cambiarla o sumar otra, pasá la conversación a una persona."
        )
    day_start = starts.astimezone(zone).replace(hour=0, minute=0, second=0, microsecond=0)
    if starts not in await _free_slots(session, run, day_start, days=1):
        raise _Refused("Ese horario no está libre. Consultá list_free_times.")
    product = await _product_named(session, account_id, args.get("product"))
    title = product.name if product is not None else t(DEFAULT_LOCALE, "ai_agent.appointment_title")
    when = starts.astimezone(zone).strftime("%Y-%m-%d %H:%M")
    if run.live:
        await create_appointment(
            session,
            account_id=account_id,
            payload={
                "title": title,
                "contact_id": run.conversation.contact_id,
                "product_id": product.id if product is not None else None,
                "starts_at": starts,
                "ends_at": starts + timedelta(minutes=run.config.slot_minutes),
                "description": t(
                    DEFAULT_LOCALE, "ai_agent.appointment_note", n=run.conversation.display_id
                ),
            },
        )
    await _act(session, run, t(DEFAULT_LOCALE, "ai_agent.action.book", title=title, when=when))
    return {"booked": True, "title": title, "starts_at": starts.astimezone(zone).isoformat()}


# ---------------------------------------------------------------------------
# CRM
# ---------------------------------------------------------------------------
async def _save_contact(session: AsyncSession, run: ToolRun, args: dict[str, Any]) -> dict[str, Any]:
    from app.domains.contacts.models import Contact

    contact = await session.get(Contact, run.conversation.contact_id)
    if contact is None:
        raise _Refused("No hay contacto.")
    changes: dict[str, str] = {}
    name = " ".join(str(args.get("name") or "").split())[:80]
    # Only what's missing: a name never set (or just the phone), an email.
    if name and (not (contact.name or "").strip() or contact.name == contact.phone_number):
        changes["name"] = name
    email = str(args.get("email") or "").strip().lower()[:255]
    if email:
        if not _EMAIL.match(email):
            raise _Refused("El email no es válido.")
        if not contact.email:
            taken = (
                await session.exec(
                    select(Contact.id).where(
                        Contact.account_id == contact.account_id,
                        func.lower(Contact.email) == email,
                    )
                )
            ).first()
            if taken is not None:
                raise _Refused("Ese email ya es de otro contacto: pasá la conversación a una persona.")
            changes["email"] = email
    if not changes:
        return {"saved": False, "reason": "Ya tenía esos datos."}
    if run.live:
        for key, value in changes.items():
            setattr(contact, key, value)
        if "email" in changes:
            # Typed in a chat, never confirmed: people can tell.
            contact.additional_attributes = {
                **(contact.additional_attributes or {}),
                "email_from_ai": True,
            }
        session.add(contact)
        await session.flush()
    fields = ", ".join(f"{k}: {v}" for k, v in changes.items())
    await _act(session, run, t(DEFAULT_LOCALE, "ai_agent.action.contact", fields=fields))
    return {"saved": True, **changes}


async def _set_stage(session: AsyncSession, run: ToolRun, args: dict[str, Any]) -> dict[str, Any]:
    from app.domains.contacts.models import Contact
    from app.domains.lifecycle.models import KIND_STAGE, LifecycleSettings
    from app.domains.lifecycle.service import set_stage, stages_of

    settings = await session.get(LifecycleSettings, run.conversation.account_id)
    if settings is None or not settings.enabled:
        raise _Refused("El negocio no usa etapas.")
    wanted = str(args.get("stage") or "").strip().lower()
    stages = [s for s in stages_of(settings) if s.get("kind", KIND_STAGE) == KIND_STAGE]
    stage = next(
        (s for s in stages if wanted in (str(s["key"]).lower(), str(s.get("name") or "").lower())),
        None,
    )
    if stage is None:
        names = ", ".join(str(s.get("name") or s["key"]) for s in stages)
        raise _Refused(f"No existe esa etapa. Hay: {names}.")
    label = f"{stage.get('emoji') or ''} {stage.get('name') or stage['key']}".strip()
    if run.live:
        contact = await session.get(Contact, run.conversation.contact_id)
        if contact is None:
            raise _Refused("No hay contacto.")
        await set_stage(
            session,
            account_id=run.conversation.account_id,
            contact=contact,
            stage_key=stage["key"],
            user=None,
            tell_meta=False,
        )
    await _act(session, run, t(DEFAULT_LOCALE, "ai_agent.action.stage", stage=label))
    return {"stage": label}


async def _add_label(session: AsyncSession, run: ToolRun, args: dict[str, Any]) -> dict[str, Any]:
    from app.domains.conversations.service import update_labels
    from app.domains.labels.models import Label

    wanted = str(args.get("label") or "").strip().lower()
    titles = list(
        (await session.exec(select(Label.title).where(Label.account_id == run.conversation.account_id))).all()
    )
    title = next((x for x in titles if x and x.lower() == wanted), None)
    if title is None:
        # The account's labels aren't listed: some are internal.
        raise _Refused("No existe esa etiqueta.")
    current = [s.strip() for s in (run.conversation.cached_label_list or "").split(",") if s.strip()]
    if title.lower() in (c.lower() for c in current):
        return {"label": title, "already": True}
    if run.live:
        await update_labels(session, conversation=run.conversation, titles=[*current, title])
    await _act(session, run, t(DEFAULT_LOCALE, "ai_agent.action.label", label=title))
    return {"label": title}


async def _create_opportunity(session: AsyncSession, run: ToolRun, args: dict[str, Any]) -> dict[str, Any]:
    from app.domains.crm.service import save_opportunity

    title = str(args.get("title") or "").strip()[:255]
    if not title:
        raise _Refused("Falta el título.")
    account_id = run.conversation.account_id
    product = await _product_named(session, account_id, args.get("product"))
    value = args.get("value")
    if value is not None and (isinstance(value, bool) or not isinstance(value, int | float) or value < 0):
        raise _Refused("value tiene que ser un número.")
    if run.live:
        await save_opportunity(
            session,
            account_id=account_id,
            opportunity=None,
            payload={
                "title": title,
                "contact_id": run.conversation.contact_id,
                "conversation_id": run.conversation.id,
                **({"product_id": product.id} if product is not None else {}),
                **({"value": value} if value is not None else {}),
            },
        )
    await _act(session, run, t(DEFAULT_LOCALE, "ai_agent.action.opportunity", title=title))
    return {"created": True, "title": title}


_HANDLERS = {
    TOOL_SEARCH: _search_help_center,
    TOOL_PRODUCTS: _products,
    TOOL_FREE_TIMES: _list_free_times,
    TOOL_BOOK: _book,
    TOOL_CONTACT: _save_contact,
    TOOL_STAGE: _set_stage,
    TOOL_LABEL: _add_label,
    TOOL_OPPORTUNITY: _create_opportunity,
}


__all__ = ["TOOL_HANDOFF", "ToolRun", "dump", "run_tool", "specs_for"]
