"""Seed synthetic history into the local dev DB so the Reportes screens have
something to show.

Rows are inserted directly (not through the domain services) because every
timestamp has to land in the past — the services stamp ``now()`` and would
also fire listeners that try to send real outbound messages.

Shape of the dataset: two consecutive 30-day windows so the "vs. período
previo" deltas are meaningful, with the recent window busier than the older
one. Conversations are weighted toward weekday business hours so the traffic
heatmap looks like a real support desk rather than white noise.

Idempotent-ish: everything it creates is tagged with SEED_MARK, and a
``--reset`` flag removes exactly those rows before re-seeding.
"""

from __future__ import annotations

import asyncio
import logging
import random
import sys
import uuid
from datetime import UTC, datetime, timedelta
from functools import partial

from sqlmodel import delete, select

import app.main  # noqa: F401  — closes the SQLAlchemy mapper registry
from app.core.db import get_session_factory
from app.domains.accounts.models import Account
from app.domains.contacts.models import Contact, ContactInbox
from app.domains.conversations.models import (
    CONVERSATION_STATUS_OPEN,
    CONVERSATION_STATUS_PENDING,
    CONVERSATION_STATUS_RESOLVED,
    MESSAGE_TYPE_INCOMING,
    MESSAGE_TYPE_OUTGOING,
    Conversation,
    ConversationLabel,
    Message,
)
from app.domains.csat.models import CsatSurveyResponse
from app.domains.inboxes.models import (
    Inbox,
    InstagramChannel,
    WebWidget,
    WhatsappChannel,
)
from app.domains.labels.models import Label
from app.domains.reporting.models import ReportingEvent
from app.domains.teams.models import Team, TeamMember
from app.domains.users.models import AccountUser, User

logging.disable(logging.CRITICAL)  # the app is chatty on import; this is a script

SEED_MARK = "seed-demo"
ACCOUNT_ID = 2
RNG = random.Random(20260726)  # fixed seed → reproducible dataset

AGENTS = [
    ("Ana Rodríguez", "ana.demo@alostudio.test"),
    ("Bruno Sosa", "bruno.demo@alostudio.test"),
    ("Carla Méndez", "carla.demo@alostudio.test"),
    ("Diego Fernández", "diego.demo@alostudio.test"),
    ("Elena Vargas", "elena.demo@alostudio.test"),
]
TEAMS = ["Ventas", "Soporte", "Postventa"]
LABELS = [
    ("consulta", "#2563eb"), ("presupuesto", "#0b9d63"), ("reclamo", "#d9344a"),
    ("vip", "#fcd535"), ("envio", "#8b5cf6"),
]
FIRST = ["Lucía", "Martín", "Sofía", "Joaquín", "Valentina", "Mateo", "Camila",
         "Nicolás", "Julieta", "Facundo", "Agustina", "Tomás", "Florencia",
         "Ignacio", "Micaela", "Santiago", "Rocío", "Gonzalo", "Paula", "Emilia"]
LAST = ["González", "Pérez", "Silva", "Romero", "Díaz", "Castro", "Ortiz",
        "Núñez", "Ramos", "Herrera", "Molina", "Acosta"]

ASKS = [
    "Hola, ¿hacen envíos al interior?",
    "Buenas, quería saber el precio del pack grande.",
    "No me llegó el pedido todavía, ¿me ayudan?",
    "¿Tienen stock del modelo azul?",
    "Quiero cambiar la dirección de entrega.",
    "¿Aceptan transferencia bancaria?",
    "Me llegó dañado, ¿cómo hago el cambio?",
    "¿Cuánto demora el envío a Córdoba?",
    "¿Puedo pagar en cuotas?",
    "Necesito la factura del pedido de la semana pasada.",
]
REPLIES = [
    "¡Hola! Sí, enviamos a todo el país. ¿A qué localidad sería?",
    "Buenas, te paso el detalle de precios ahora mismo.",
    "Perdón por la demora — lo reviso y te confirmo en un momento.",
    "Sí, tenemos stock. ¿Te reservo una unidad?",
    "Claro, decime la dirección nueva y la actualizo.",
    "Sí, aceptamos transferencia. Te paso los datos.",
]
FEEDBACK = [
    "Muy buena atención, rapidísimos.", "Todo bien, gracias.",
    "Tardaron un poco pero resolvieron.", "Excelente, super amables.",
    "Me resolvieron el problema enseguida.", None, None,
]


def make_event(
    name: str,
    value: float,
    ts: datetime,
    *,
    conv_id: int,
    inbox_id: int,
    agent_id: int,
    started: datetime,
) -> ReportingEvent:
    """One reporting_events row — this is what the timing metrics average.

    Module-level (rather than a closure inside the seeding loop) so the
    per-conversation values are bound explicitly via ``partial``.
    """
    return ReportingEvent(
        account_id=ACCOUNT_ID, conversation_id=conv_id, inbox_id=inbox_id,
        user_id=agent_id, name=name, value=value,
        value_in_business_hours=value * RNG.uniform(0.55, 0.95),
        event_start_time=started, event_end_time=ts,
        created_at=ts, updated_at=ts,
    )


def business_ts(day: datetime) -> datetime:
    """A timestamp inside `day`, weighted toward weekday business hours."""
    if day.weekday() >= 5 and RNG.random() < 0.72:
        day += timedelta(days=(7 - day.weekday()))  # push most weekend load to Monday
    hour = RNG.choices(
        population=list(range(24)),
        weights=[1, 1, 1, 1, 1, 2, 4, 8, 16, 26, 30, 28, 22, 20, 26, 28, 25, 20, 14, 9, 6, 4, 2, 1],
    )[0]
    return day.replace(hour=hour, minute=RNG.randrange(60), second=RNG.randrange(60),
                       microsecond=0, tzinfo=UTC)


async def reset(s) -> None:
    """Delete only what a previous run of this script created."""
    # ``identifier`` is unique per account, so each seeded row carries
    # ``seed-demo-<n>`` rather than a shared marker; match on the prefix.
    convs = (await s.exec(
        select(Conversation.id).where(
            Conversation.account_id == ACCOUNT_ID,
            Conversation.identifier.like(f"{SEED_MARK}-%"),
        )
    )).all()
    if convs:
        for model in (ReportingEvent, CsatSurveyResponse, ConversationLabel, Message):
            await s.exec(delete(model).where(model.conversation_id.in_(convs)))
        await s.exec(delete(Conversation).where(Conversation.id.in_(convs)))
    contacts = (await s.exec(
        select(Contact.id).where(Contact.account_id == ACCOUNT_ID,
                                 Contact.identifier.like(f"{SEED_MARK}-%"))
    )).all()
    if contacts:
        await s.exec(delete(ContactInbox).where(ContactInbox.contact_id.in_(contacts)))
        await s.exec(delete(Contact).where(Contact.id.in_(contacts)))
    await s.commit()
    print(f"  reset: {len(convs)} conversaciones y {len(contacts)} contactos eliminados")


async def main() -> None:
    do_reset = "--reset" in sys.argv
    async with get_session_factory()() as s:
        acct = await s.get(Account, ACCOUNT_ID)
        if acct is None:
            print(f"!! no existe la cuenta {ACCOUNT_ID}")
            return
        print(f"cuenta: {acct.name!r}")

        if do_reset:
            await reset(s)

        # ---------- agents ----------
        agent_ids: list[int] = []
        for name, email in AGENTS:
            u = (await s.exec(select(User).where(User.email == email))).first()
            if u is None:
                u = User(name=name, email=email, display_name=name.split()[0],
                         encrypted_password="x" * 20, provider="email", uid=email)
                s.add(u)
                await s.flush()
                s.add(AccountUser(account_id=ACCOUNT_ID, user_id=u.id, role=0))
            agent_ids.append(u.id)
        await s.flush()
        print(f"  agentes: {len(agent_ids)}")

        # ---------- teams ----------
        team_ids: list[int] = []
        for i, tname in enumerate(TEAMS):
            t = (await s.exec(select(Team).where(Team.account_id == ACCOUNT_ID,
                                                 Team.name == tname))).first()
            if t is None:
                t = Team(name=tname, account_id=ACCOUNT_ID, allow_auto_assign=True,
                         description=f"Equipo de {tname}")
                s.add(t)
                await s.flush()
                for uid in agent_ids[i::len(TEAMS)] or agent_ids[:1]:
                    s.add(TeamMember(team_id=t.id, user_id=uid))
            team_ids.append(t.id)
        await s.flush()
        print(f"  equipos: {len(team_ids)}")

        # ---------- labels ----------
        label_ids: list[int] = []
        for title, color in LABELS:
            lbl = (await s.exec(select(Label).where(Label.account_id == ACCOUNT_ID,
                                                    Label.title == title))).first()
            if lbl is None:
                lbl = Label(title=title, color=color, account_id=ACCOUNT_ID,
                            show_on_sidebar=True, description=f"Etiqueta {title}")
                s.add(lbl)
                await s.flush()
            label_ids.append(lbl.id)
        print(f"  etiquetas: {len(label_ids)}")

        # ---------- inboxes (one per channel so the breakdown has variety) ----------
        async def ensure_inbox(name: str, channel_type: str, channel) -> int:
            ib = (await s.exec(select(Inbox).where(Inbox.account_id == ACCOUNT_ID,
                                                   Inbox.name == name))).first()
            if ib is not None:
                return ib.id
            s.add(channel)
            await s.flush()
            ib = Inbox(account_id=ACCOUNT_ID, name=name,
                       channel_type=channel_type, channel_id=channel.id)
            s.add(ib)
            await s.flush()
            return ib.id

        inbox_ids = [
            await ensure_inbox("WhatsApp Ventas", "Channel::Whatsapp",
                               WhatsappChannel(account_id=ACCOUNT_ID,
                                               phone_number="+5490000000001",
                                               provider="whatsapp_cloud",
                                               provider_config={})),
            await ensure_inbox("Instagram @tienda", "Channel::Instagram",
                               InstagramChannel(account_id=ACCOUNT_ID,
                                                instagram_id="demo-ig-0001",
                                                access_token="demo",
                                                expires_at=datetime.now(UTC) + timedelta(days=60))),
            await ensure_inbox("Chat del sitio", "Channel::WebWidget",
                               WebWidget(account_id=ACCOUNT_ID,
                                         website_url="https://tienda.demo",
                                         website_token=uuid.uuid4().hex[:20],
                                         hmac_token=uuid.uuid4().hex[:20])),
        ]
        existing = (await s.exec(select(Inbox).where(Inbox.account_id == ACCOUNT_ID))).all()
        api_ib = next((i.id for i in existing if i.channel_type == "Channel::Api"), None)
        if api_ib:
            inbox_ids.append(api_ib)
        await s.commit()
        print(f"  bandejas: {len(inbox_ids)}")

        # ---------- conversations over two 30-day windows ----------
        now = datetime.now(UTC)
        max_display = (await s.exec(
            select(Conversation.display_id).where(Conversation.account_id == ACCOUNT_ID)
            .order_by(Conversation.display_id.desc()).limit(1)
        )).first() or 0

        windows = [(60, 31, 58), (30, 0, 86)]  # (desde, hasta, cantidad) — el reciente crece
        made = resolved_n = 0
        display = max_display

        for days_from, days_to, count in windows:
            for _ in range(count):
                offset = RNG.uniform(days_to, days_from)
                opened = business_ts(now - timedelta(days=offset))
                if opened > now:
                    continue

                display += 1
                inbox_id = RNG.choices(inbox_ids, weights=[40, 25, 25, 10][:len(inbox_ids)])[0]
                agent_id = RNG.choices(agent_ids, weights=[26, 22, 20, 18, 14])[0]
                team_id = RNG.choice(team_ids)

                contact = Contact(
                    account_id=ACCOUNT_ID, identifier=f"{SEED_MARK}-{display}",
                    name=f"{RNG.choice(FIRST)} {RNG.choice(LAST)}",
                    email=f"c{display}@demo.test",
                    phone_number=f"+54911{RNG.randrange(10**7):07d}",
                    created_at=opened, updated_at=opened,
                )
                s.add(contact)
                await s.flush()
                ci = ContactInbox(contact_id=contact.id, inbox_id=inbox_id,
                                  source_id=f"{SEED_MARK}-{display}",
                                  pubsub_token=uuid.uuid4().hex,
                                  created_at=opened, updated_at=opened)
                s.add(ci)
                await s.flush()

                # timings
                frt = RNG.choice([RNG.uniform(60, 480), RNG.uniform(120, 900),
                                  RNG.uniform(900, 3000)])
                will_resolve = RNG.random() < 0.78
                res_secs = RNG.choice([RNG.uniform(900, 5400), RNG.uniform(3600, 21600),
                                       RNG.uniform(7200, 50000)])
                first_reply_at = opened + timedelta(seconds=frt)
                resolved_at = first_reply_at + timedelta(seconds=res_secs)
                if resolved_at > now:
                    will_resolve = False

                status = (CONVERSATION_STATUS_RESOLVED if will_resolve
                          else RNG.choices([CONVERSATION_STATUS_OPEN,
                                            CONVERSATION_STATUS_PENDING],
                                           weights=[75, 25])[0])
                last_act = resolved_at if will_resolve else first_reply_at

                conv = Conversation(
                    account_id=ACCOUNT_ID, inbox_id=inbox_id, contact_id=contact.id,
                    contact_inbox_id=ci.id, assignee_id=agent_id, team_id=team_id,
                    display_id=display, uuid=str(uuid.uuid4()), status=status,
                    identifier=f"{SEED_MARK}-{display}",
                    priority=RNG.choices([None, 0, 1, 2, 3], weights=[55, 8, 15, 15, 7])[0],
                    first_reply_created_at=first_reply_at,
                    last_activity_at=last_act,
                    created_at=opened, updated_at=last_act,
                )
                s.add(conv)
                await s.flush()

                # messages
                msgs = [(MESSAGE_TYPE_INCOMING, RNG.choice(ASKS), opened, "Contact", contact.id),
                        (MESSAGE_TYPE_OUTGOING, RNG.choice(REPLIES), first_reply_at, "User", agent_id)]
                t = first_reply_at
                for _ in range(RNG.randrange(0, 5)):
                    t += timedelta(seconds=RNG.uniform(120, 2400))
                    if t > now:
                        break
                    incoming = RNG.random() < 0.5
                    msgs.append((MESSAGE_TYPE_INCOMING if incoming else MESSAGE_TYPE_OUTGOING,
                                 RNG.choice(ASKS if incoming else REPLIES), t,
                                 "Contact" if incoming else "User",
                                 contact.id if incoming else agent_id))
                for mtype, content, ts, stype, sid in msgs:
                    s.add(Message(account_id=ACCOUNT_ID, inbox_id=inbox_id,
                                  conversation_id=conv.id, message_type=mtype,
                                  content=content, sender_type=stype, sender_id=sid,
                                  private=False, created_at=ts, updated_at=ts))

                # labels
                for lid in RNG.sample(label_ids, RNG.randrange(1, 3)):
                    s.add(ConversationLabel(conversation_id=conv.id, label_id=lid,
                                            created_at=opened, updated_at=opened))

                # reporting events — these are what the timing metrics average
                ev = partial(make_event, conv_id=conv.id, inbox_id=inbox_id,
                             agent_id=agent_id, started=opened)

                s.add(ev("first_response", frt, first_reply_at))
                s.add(ev("reply_time", RNG.uniform(120, 1500), first_reply_at))
                if will_resolve:
                    resolved_n += 1
                    s.add(ev("conversation_resolved", res_secs, resolved_at))
                    if RNG.random() < 0.45:  # CSAT on some resolved chats
                        # The response hangs off the survey message the bot
                        # sends on resolve, so that row has to exist first.
                        survey = Message(
                            account_id=ACCOUNT_ID, inbox_id=inbox_id,
                            conversation_id=conv.id, message_type=MESSAGE_TYPE_OUTGOING,
                            content="¿Cómo calificarías la atención recibida?",
                            # INPUT_CSAT — the CSAT report counts these as the
                            # denominator for its response rate.
                            content_type=9, sender_type="User", sender_id=agent_id,
                            private=False, created_at=resolved_at, updated_at=resolved_at,
                        )
                        s.add(survey)
                        await s.flush()
                        s.add(CsatSurveyResponse(
                            account_id=ACCOUNT_ID, conversation_id=conv.id,
                            message_id=survey.id,
                            contact_id=contact.id, assigned_agent_id=agent_id,
                            rating=RNG.choices([5, 4, 3, 2, 1], weights=[46, 27, 14, 8, 5])[0],
                            feedback_message=RNG.choice(FEEDBACK),
                            created_at=resolved_at, updated_at=resolved_at,
                        ))
                    if RNG.random() < 0.18:  # a slice handled by the bot
                        s.add(ev("conversation_bot_resolved", res_secs, resolved_at))
                    elif RNG.random() < 0.12:
                        s.add(ev("conversation_bot_handoff", frt, first_reply_at))

                made += 1
            await s.commit()

        print(f"  conversaciones creadas: {made} (resueltas: {resolved_n})")
        print("listo.")


asyncio.run(main())
