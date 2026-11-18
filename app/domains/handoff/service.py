"""Who takes a handed-off conversation (see :mod:`app.domains.handoff.models`).

:func:`resolve_target` walks the levels (chat, labels, inbox, account) and
returns the first usable one; ``bot_handoff`` assigns it. The rest saves
and shows the rules for Ajustes → Derivación and the conversation panel.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlmodel import delete, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.i18n import DEFAULT_LOCALE, t
from app.domains.agent_bots.models import AGENT_BOT_TYPE_AI, AgentBot
from app.domains.contacts.models import Contact
from app.domains.conversations.models import Conversation
from app.domains.handoff.models import (
    SCOPE_ACCOUNT,
    SCOPE_CONTACT,
    SCOPE_LABEL,
    HandoffRule,
)
from app.domains.inboxes.models import Inbox
from app.domains.labels.models import Label
from app.domains.users.models import AccountUser

LABEL_RULES_MAX = 50


@dataclass(frozen=True, slots=True)
class HandoffTarget:
    """Where a handoff goes, and why (for the line it leaves)."""

    user_id: int | None
    to_ai: bool
    source: str  # "contact" | "label" | "inbox" | "account"
    label: str | None = None


async def ai_available(session: AsyncSession, account_id: int) -> bool:
    """Whether the account has AloStudio's AI to hand conversations to
    (paso 2b). On a multitenant install the plan decides too."""
    bot = (
        await session.exec(
            select(AgentBot.id).where(
                AgentBot.account_id == account_id, AgentBot.bot_type == AGENT_BOT_TYPE_AI
            )
        )
    ).first()
    return bot is not None


async def _member_ids(session: AsyncSession, account_id: int) -> set[int]:
    return set(
        (
            await session.exec(select(AccountUser.user_id).where(AccountUser.account_id == account_id))
        ).all()
    )


def _labels_of(conversation: Conversation) -> list[str]:
    raw = conversation.cached_label_list or ""
    return [s.strip() for s in raw.split(",") if s.strip()]


async def resolve_target(
    session: AsyncSession, conversation: Conversation, *, allow_ai: bool
) -> HandoffTarget | None:
    """The responsible for this handoff, or None (nobody: the inbox is
    told). ``allow_ai`` is False when the AI itself hands off: it then
    skips any level that names the AI."""
    account_id = conversation.account_id
    rules = list(
        (
            await session.exec(
                select(HandoffRule).where(
                    HandoffRule.account_id == account_id,
                    or_(
                        HandoffRule.scope != SCOPE_CONTACT,
                        HandoffRule.contact_id == conversation.contact_id,
                    ),
                )
            )
        ).all()
    )
    members = await _member_ids(session, account_id)
    ai_ok = allow_ai and await ai_available(session, account_id)

    def usable(user_id: int | None, to_ai: bool) -> bool:
        return ai_ok if to_ai else user_id is not None and user_id in members

    contact_rule = next(
        (r for r in rules if r.scope == SCOPE_CONTACT and r.contact_id == conversation.contact_id),
        None,
    )
    if contact_rule is not None and usable(contact_rule.user_id, contact_rule.to_ai):
        return HandoffTarget(contact_rule.user_id, contact_rule.to_ai, SCOPE_CONTACT)

    label_rules = sorted((r for r in rules if r.scope == SCOPE_LABEL), key=lambda r: (r.position, r.id or 0))
    carried = {name.lower() for name in _labels_of(conversation)}
    if label_rules and carried:
        titles = dict(
            (
                await session.exec(
                    select(Label.id, Label.title).where(
                        Label.id.in_([r.label_id for r in label_rules])  # type: ignore[union-attr]
                    )
                )
            ).all()
        )
        for rule in label_rules:
            title = titles.get(rule.label_id)  # type: ignore[arg-type]
            if title and title.lower() in carried and usable(rule.user_id, rule.to_ai):
                return HandoffTarget(rule.user_id, rule.to_ai, SCOPE_LABEL, label=title)

    inbox = await session.get(Inbox, conversation.inbox_id)
    if inbox is not None and usable(inbox.handoff_assignee_id, False):
        return HandoffTarget(inbox.handoff_assignee_id, False, "inbox")

    account_rule = next((r for r in rules if r.scope == SCOPE_ACCOUNT), None)
    if account_rule is not None and usable(account_rule.user_id, account_rule.to_ai):
        return HandoffTarget(account_rule.user_id, account_rule.to_ai, SCOPE_ACCOUNT)
    return None


def activity_text(target: HandoffTarget) -> str | None:
    """Why the handoff went where it did, next to the assignment line
    (``update_assignee`` already names the person). The inbox level was
    there before the rules and keeps leaving no extra line."""
    if target.source == "inbox":
        return None
    return t(DEFAULT_LOCALE, f"handoff.activity.{target.source}", label=target.label or "")


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
def present_target(
    rule: HandoffRule | None, members: set[int] | None = None
) -> dict[str, Any] | None:
    """A rule's target for the panel. With ``members``, a person who left
    the account shows as no one, so the admin picks someone else instead
    of a save that keeps failing."""
    if rule is None:
        return None
    user_id = rule.user_id
    if members is not None and user_id not in members:
        user_id = None
    return {"user_id": user_id, "to_ai": rule.to_ai}


async def present_rules(session: AsyncSession, account_id: int) -> dict[str, Any]:
    rules = list(
        (
            await session.exec(
                select(HandoffRule).where(
                    HandoffRule.account_id == account_id, HandoffRule.scope != SCOPE_CONTACT
                )
            )
        ).all()
    )
    members = await _member_ids(session, account_id)
    account_rule = next((r for r in rules if r.scope == SCOPE_ACCOUNT), None)
    label_rules = sorted((r for r in rules if r.scope == SCOPE_LABEL), key=lambda r: (r.position, r.id or 0))
    return {
        "account": present_target(account_rule, members),
        "labels": [
            {"label_id": r.label_id, **(present_target(r, members) or {})} for r in label_rules
        ],
        "ai_available": await ai_available(session, account_id),
    }


@dataclass(slots=True)
class _Checker:
    """Validates targets, loading the members and the AI once."""

    session: AsyncSession
    account_id: int
    _members: set[int] | None = None
    _ai: bool | None = None

    async def check(self, user_id: int | None, to_ai: bool) -> None:
        """``ValueError`` with a code for the panel when the target can't be."""
        if to_ai and user_id is not None:
            raise ValueError("one_target")
        if to_ai:
            if self._ai is None:
                self._ai = await ai_available(self.session, self.account_id)
            if not self._ai:
                raise ValueError("ai_unavailable")
        if user_id is not None:
            if self._members is None:
                self._members = await _member_ids(self.session, self.account_id)
            if user_id not in self._members:
                raise ValueError("not_a_member")


async def save_rules(
    session: AsyncSession,
    *,
    account_id: int,
    account: dict[str, Any],
    labels: list[dict[str, Any]],
) -> dict[str, Any]:
    """Replace the account rule and the label rules (their order is their
    priority). Everything is checked before anything is written."""
    checker = _Checker(session, account_id)
    account_user, account_ai = account.get("user_id"), bool(account.get("to_ai"))
    await checker.check(account_user, account_ai)
    if len(labels) > LABEL_RULES_MAX:
        raise ValueError("too_many")
    label_ids = [r.get("label_id") for r in labels]
    if len(set(label_ids)) != len(label_ids):
        raise ValueError("repeated_label")
    known = set(
        (
            await session.exec(
                select(Label.id).where(
                    Label.account_id == account_id,
                    Label.id.in_([i for i in label_ids if isinstance(i, int)]),  # type: ignore[union-attr]
                )
            )
        ).all()
    )
    for rule in labels:
        if rule.get("label_id") not in known:
            raise ValueError("unknown_label")
        user_id, to_ai = rule.get("user_id"), bool(rule.get("to_ai"))
        if user_id is None and not to_ai:
            raise ValueError("no_target")
        await checker.check(user_id, to_ai)

    await session.exec(  # type: ignore[call-overload]
        delete(HandoffRule).where(
            HandoffRule.account_id == account_id,  # type: ignore[arg-type]
            HandoffRule.scope != SCOPE_CONTACT,  # type: ignore[arg-type]
        )
    )
    await session.flush()
    if account_user is not None or account_ai:
        session.add(
            HandoffRule(
                account_id=account_id, scope=SCOPE_ACCOUNT, user_id=account_user, to_ai=account_ai
            )
        )
    for position, rule in enumerate(labels):
        session.add(
            HandoffRule(
                account_id=account_id,
                scope=SCOPE_LABEL,
                label_id=rule["label_id"],
                user_id=rule.get("user_id"),
                to_ai=bool(rule.get("to_ai")),
                position=position,
            )
        )
    await session.flush()
    return await present_rules(session, account_id)


async def present_contact_rule(session: AsyncSession, contact: Contact) -> dict[str, Any]:
    account_id = contact.account_id
    rule = await contact_rule(session, account_id=account_id, contact_id=contact.id)  # type: ignore[arg-type]
    return {
        "contact": present_target(rule, await _member_ids(session, account_id)),
        "ai_available": await ai_available(session, account_id),
    }


async def contact_rule(session: AsyncSession, *, account_id: int, contact_id: int) -> HandoffRule | None:
    return (
        await session.exec(
            select(HandoffRule).where(
                HandoffRule.account_id == account_id, HandoffRule.contact_id == contact_id
            )
        )
    ).first()


async def save_contact_rule(
    session: AsyncSession, *, contact: Contact, user_id: int | None, to_ai: bool
) -> dict[str, Any] | None:
    account_id = contact.account_id
    await _Checker(session, account_id).check(user_id, to_ai)
    rule = await contact_rule(session, account_id=account_id, contact_id=contact.id)  # type: ignore[arg-type]
    if user_id is None and not to_ai:
        if rule is not None:
            await session.delete(rule)
            await session.flush()
        return None
    if rule is None:
        rule = HandoffRule(account_id=account_id, scope=SCOPE_CONTACT, contact_id=contact.id)
    rule.user_id, rule.to_ai = user_id, to_ai
    session.add(rule)
    await session.flush()
    return present_target(rule)


__all__ = [
    "HandoffTarget",
    "activity_text",
    "ai_available",
    "contact_rule",
    "present_contact_rule",
    "present_rules",
    "present_target",
    "resolve_target",
    "save_contact_rule",
    "save_rules",
]
