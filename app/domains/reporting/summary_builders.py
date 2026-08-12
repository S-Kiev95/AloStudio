"""Per-entity summary report builders.

Ported from:
  reference/chatwoot/app/builders/v2/reports/base_summary_builder.rb
  reference/chatwoot/app/builders/v2/reports/agent_summary_builder.rb
  reference/chatwoot/app/builders/v2/reports/team_summary_builder.rb
  reference/chatwoot/app/builders/v2/reports/inbox_summary_builder.rb
  reference/chatwoot/app/builders/v2/reports/label_summary_builder.rb

Each builder returns ``[{id, conversations_count,
resolved_conversations_count, avg_resolution_time,
avg_first_response_time, avg_reply_time}, ...]`` — one row per entity
in the account.

Agent / team / inbox builders group by the column on ReportingEvent
(``user_id`` / via conversation.team_id / ``inbox_id``).
Label builder joins ReportingEvent → Conversation → ConversationLabel
since labels don't live directly on ReportingEvent.

``business_hours=True`` swaps the value column to
``value_in_business_hours`` (no-op until Phase 9).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Float,
)
from sqlalchemy import (
    case as sa_case,
)
from sqlalchemy import (
    cast as sa_cast,
)
from sqlalchemy import (
    func as sa_func,
)
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.conversations.models import (
    Conversation,
    ConversationLabel,
)
from app.domains.inboxes.models import Inbox
from app.domains.labels.models import Label
from app.domains.reporting.models import ReportingEvent
from app.domains.teams.models import Team
from app.domains.users.models import AccountUser, User


def _value_column(business_hours: bool):
    return (
        ReportingEvent.value_in_business_hours
        if business_hours
        else ReportingEvent.value
    )


def _empty_row(entity_id: int, *, name: str | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": entity_id,
        "conversations_count": 0,
        "resolved_conversations_count": 0,
        "avg_resolution_time": 0,
        "avg_first_response_time": 0,
        "avg_reply_time": 0,
    }
    if name is not None:
        row["name"] = name
    return row


# ---------------------------------------------------------------------------
# Shared aggregation helpers
# ---------------------------------------------------------------------------
async def _conversation_counts_by(
    session: AsyncSession,
    *,
    group_col,
    account_id: int,
    since: datetime | None,
    until: datetime | None,
    extra_filter=None,
) -> dict[Any, int]:
    """Count conversations grouped by ``group_col`` (Conversation.<col>).

    ``extra_filter`` lets the label builder thread its join +
    ``ConversationLabel.label_id`` group through.
    """
    stmt = select(
        group_col.label("group"),
        sa_func.count(sa_func.distinct(Conversation.id)).label("count"),
    ).where(Conversation.account_id == account_id)
    if since is not None:
        stmt = stmt.where(Conversation.created_at >= since)
    if until is not None:
        stmt = stmt.where(Conversation.created_at <= until)
    if extra_filter is not None:
        stmt = extra_filter(stmt)
    stmt = stmt.group_by(group_col)
    rows = list((await session.exec(stmt)).all())
    return {row[0]: int(row[1] or 0) for row in rows if row[0] is not None}


async def _reporting_metrics_by(
    session: AsyncSession,
    *,
    group_col,
    account_id: int,
    since: datetime | None,
    until: datetime | None,
    business_hours: bool,
    extra_filter=None,
) -> tuple[
    dict[Any, int],
    dict[Any, float],
    dict[Any, float],
    dict[Any, float],
]:
    """Bulk aggregate over reporting_events grouped by ``group_col``.

    Mirrors the four columns Chatwoot's BaseSummaryBuilder computes in
    one SQL statement:
      * resolved_count (count of conversation_resolved rows)
      * avg_resolution_time (avg value over conversation_resolved)
      * avg_first_response_time (avg value over first_response)
      * avg_reply_time (avg value over reply_time)
    """
    value = _value_column(business_hours)
    resolved_count = sa_func.count(
        sa_case(
            (ReportingEvent.name == "conversation_resolved", 1),
            else_=None,
        )
    )
    avg_resolution = sa_func.avg(
        sa_case(
            (
                ReportingEvent.name == "conversation_resolved",
                sa_cast(value, Float),
            ),
            else_=None,
        )
    )
    avg_first_response = sa_func.avg(
        sa_case(
            (
                ReportingEvent.name == "first_response",
                sa_cast(value, Float),
            ),
            else_=None,
        )
    )
    avg_reply = sa_func.avg(
        sa_case(
            (
                ReportingEvent.name == "reply_time",
                sa_cast(value, Float),
            ),
            else_=None,
        )
    )

    stmt = select(
        group_col.label("group"),
        resolved_count.label("resolved"),
        avg_resolution.label("avg_resolution"),
        avg_first_response.label("avg_first_response"),
        avg_reply.label("avg_reply"),
    ).where(ReportingEvent.account_id == account_id)
    if since is not None:
        stmt = stmt.where(ReportingEvent.created_at >= since)
    if until is not None:
        stmt = stmt.where(ReportingEvent.created_at <= until)
    if extra_filter is not None:
        stmt = extra_filter(stmt)
    stmt = stmt.group_by(group_col)
    rows = list((await session.exec(stmt)).all())

    resolved_map: dict[Any, int] = {}
    avg_res_map: dict[Any, float] = {}
    avg_fr_map: dict[Any, float] = {}
    avg_rt_map: dict[Any, float] = {}
    for row in rows:
        key = row[0]
        if key is None:
            continue
        resolved_map[key] = int(row[1] or 0)
        avg_res_map[key] = float(row[2]) if row[2] is not None else 0.0
        avg_fr_map[key] = float(row[3]) if row[3] is not None else 0.0
        avg_rt_map[key] = float(row[4]) if row[4] is not None else 0.0
    return resolved_map, avg_res_map, avg_fr_map, avg_rt_map


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------
async def build_agent_summary(
    session: AsyncSession,
    *,
    account_id: int,
    since: datetime | None,
    until: datetime | None,
    business_hours: bool = False,
) -> list[dict[str, Any]]:
    conv_counts = await _conversation_counts_by(
        session,
        group_col=Conversation.assignee_id,
        account_id=account_id,
        since=since,
        until=until,
    )
    resolved, avg_res, avg_fr, avg_rt = await _reporting_metrics_by(
        session,
        group_col=ReportingEvent.user_id,
        account_id=account_id,
        since=since,
        until=until,
        business_hours=business_hours,
    )

    # Every AccountUser yields a row (even with zero activity) — matches
    # Rails' ``account.account_users.map``.
    rows = list(
        (
            await session.exec(
                select(AccountUser).where(
                    AccountUser.account_id == account_id
                )
            )
        ).all()
    )
    out: list[dict[str, Any]] = []
    for au in rows:
        uid = au.user_id
        out.append(
            {
                "id": uid,
                "conversations_count": conv_counts.get(uid, 0),
                "resolved_conversations_count": resolved.get(uid, 0),
                "avg_resolution_time": avg_res.get(uid, 0.0),
                "avg_first_response_time": avg_fr.get(uid, 0.0),
                "avg_reply_time": avg_rt.get(uid, 0.0),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Team
# ---------------------------------------------------------------------------
async def build_team_summary(
    session: AsyncSession,
    *,
    account_id: int,
    since: datetime | None,
    until: datetime | None,
    business_hours: bool = False,
) -> list[dict[str, Any]]:
    conv_counts = await _conversation_counts_by(
        session,
        group_col=Conversation.team_id,
        account_id=account_id,
        since=since,
        until=until,
    )

    # Reporting metrics need a join through conversation.team_id since
    # the team isn't stamped on ReportingEvent directly.
    def join(stmt):
        return stmt.join(
            Conversation,
            Conversation.id == ReportingEvent.conversation_id,
        )

    resolved, avg_res, avg_fr, avg_rt = await _reporting_metrics_by(
        session,
        group_col=Conversation.team_id,
        account_id=account_id,
        since=since,
        until=until,
        business_hours=business_hours,
        extra_filter=join,
    )

    teams = list(
        (
            await session.exec(
                select(Team).where(Team.account_id == account_id)
            )
        ).all()
    )
    out: list[dict[str, Any]] = []
    for t in teams:
        tid = t.id
        out.append(
            {
                "id": tid,
                "name": t.name,
                "conversations_count": conv_counts.get(tid, 0),
                "resolved_conversations_count": resolved.get(tid, 0),
                "avg_resolution_time": avg_res.get(tid, 0.0),
                "avg_first_response_time": avg_fr.get(tid, 0.0),
                "avg_reply_time": avg_rt.get(tid, 0.0),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Inbox
# ---------------------------------------------------------------------------
async def build_inbox_summary(
    session: AsyncSession,
    *,
    account_id: int,
    since: datetime | None,
    until: datetime | None,
    business_hours: bool = False,
) -> list[dict[str, Any]]:
    conv_counts = await _conversation_counts_by(
        session,
        group_col=Conversation.inbox_id,
        account_id=account_id,
        since=since,
        until=until,
    )
    resolved, avg_res, avg_fr, avg_rt = await _reporting_metrics_by(
        session,
        group_col=ReportingEvent.inbox_id,
        account_id=account_id,
        since=since,
        until=until,
        business_hours=business_hours,
    )
    inboxes = list(
        (
            await session.exec(
                select(Inbox).where(Inbox.account_id == account_id)
            )
        ).all()
    )
    out: list[dict[str, Any]] = []
    for ib in inboxes:
        iid = ib.id
        out.append(
            {
                "id": iid,
                "name": ib.name,
                "conversations_count": conv_counts.get(iid, 0),
                "resolved_conversations_count": resolved.get(iid, 0),
                "avg_resolution_time": avg_res.get(iid, 0.0),
                "avg_first_response_time": avg_fr.get(iid, 0.0),
                "avg_reply_time": avg_rt.get(iid, 0.0),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Ad (click-to-WhatsApp / click-to-Messenger attribution)
# ---------------------------------------------------------------------------
async def build_ad_summary(
    session: AsyncSession,
    *,
    account_id: int,
    since: datetime | None,
    until: datetime | None,
    business_hours: bool = False,
) -> list[dict[str, Any]]:
    """Per-ad breakdown of attributed conversations.

    Unlike the other axes there is no table of ads to iterate — Meta owns
    that — so the rows come from the attributed conversations themselves,
    and the human label is the headline captured with the referral.
    """
    conv_counts = await _conversation_counts_by(
        session,
        group_col=Conversation.ad_id,
        account_id=account_id,
        since=since,
        until=until,
    )
    conv_counts.pop(None, None)  # unattributed conversations aren't an ad
    if not conv_counts:
        return []

    # The ad isn't stamped on ReportingEvent, so reach it through the
    # conversation — same shape the team breakdown uses.
    def join(stmt):
        return stmt.join(
            Conversation,
            Conversation.id == ReportingEvent.conversation_id,
        )

    resolved, avg_res, avg_fr, avg_rt = await _reporting_metrics_by(
        session,
        group_col=Conversation.ad_id,
        account_id=account_id,
        since=since,
        until=until,
        business_hours=business_hours,
        extra_filter=join,
    )

    # One headline per ad — the most recent wins, since an ad's creative can
    # be edited and the latest capture is the closest to what's running now.
    labels = dict(
        (
            await session.exec(
                select(Conversation.ad_id, Conversation.ad_headline)
                .where(
                    Conversation.account_id == account_id,
                    Conversation.ad_id.in_(list(conv_counts)),
                    Conversation.ad_headline.is_not(None),
                )
                .order_by(Conversation.id.asc())
            )
        ).all()
    )

    out = [
        {
            "id": ad_id,
            "name": labels.get(ad_id) or ad_id,
            "conversations_count": count,
            "resolved_conversations_count": resolved.get(ad_id, 0),
            "avg_resolution_time": avg_res.get(ad_id, 0.0),
            "avg_first_response_time": avg_fr.get(ad_id, 0.0),
            "avg_reply_time": avg_rt.get(ad_id, 0.0),
        }
        for ad_id, count in conv_counts.items()
    ]
    # Busiest ad first — the reader wants the winner, not an id ordering.
    out.sort(key=lambda r: r["conversations_count"], reverse=True)
    return out


# ---------------------------------------------------------------------------
# Label
# ---------------------------------------------------------------------------
async def build_label_summary(
    session: AsyncSession,
    *,
    account_id: int,
    since: datetime | None,
    until: datetime | None,
    business_hours: bool = False,
) -> list[dict[str, Any]]:
    """Per-label summary — joins through ConversationLabel since the
    label tag isn't on ReportingEvent directly."""

    def conv_join(stmt):
        return stmt.join(
            ConversationLabel,
            ConversationLabel.conversation_id == Conversation.id,
        )

    conv_counts = await _conversation_counts_by(
        session,
        group_col=ConversationLabel.label_id,
        account_id=account_id,
        since=since,
        until=until,
        extra_filter=conv_join,
    )

    def report_join(stmt):
        return stmt.join(
            Conversation,
            Conversation.id == ReportingEvent.conversation_id,
        ).join(
            ConversationLabel,
            ConversationLabel.conversation_id == Conversation.id,
        )

    resolved, avg_res, avg_fr, avg_rt = await _reporting_metrics_by(
        session,
        group_col=ConversationLabel.label_id,
        account_id=account_id,
        since=since,
        until=until,
        business_hours=business_hours,
        extra_filter=report_join,
    )

    labels = list(
        (
            await session.exec(
                select(Label).where(Label.account_id == account_id)
            )
        ).all()
    )
    out: list[dict[str, Any]] = []
    for lab in labels:
        lid = lab.id
        out.append(
            {
                "id": lid,
                "name": lab.title,
                "conversations_count": conv_counts.get(lid, 0),
                "resolved_conversations_count": resolved.get(lid, 0),
                "avg_resolution_time": avg_res.get(lid, 0.0),
                "avg_first_response_time": avg_fr.get(lid, 0.0),
                "avg_reply_time": avg_rt.get(lid, 0.0),
            }
        )
    return out


# Mapper-config nudge for related models referenced via reach-in.
_ = (User,)


__all__ = [
    "build_ad_summary",
    "build_agent_summary",
    "build_inbox_summary",
    "build_label_summary",
    "build_team_summary",
]
