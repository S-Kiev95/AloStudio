"""Sales pipeline service: pipelines, stages and opportunities (F11)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import ChatwootHTTPException
from app.domains.contacts.models import Contact
from app.domains.conversations.models import Conversation
from app.domains.crm.models import (
    STAGE_KINDS,
    STAGE_OPEN,
    CrmOpportunity,
    CrmPipeline,
    CrmStage,
)
from app.domains.products.models import Product
from app.domains.users.models import AccountUser

# The pipeline every account starts with. Names come from the dashboard's
# dictionary by ``code``; probabilities are the usual sales-funnel guesses.
DEFAULT_STAGES: tuple[tuple[str, str, int], ...] = (
    ("new", "open", 10),
    ("qualified", "open", 25),
    ("proposal", "open", 50),
    ("negotiation", "open", 75),
    ("won", "won", 100),
    ("lost", "lost", 0),
)


def _now() -> datetime:
    return datetime.now(UTC)


def _unprocessable(message: str) -> ChatwootHTTPException:
    return ChatwootHTTPException(status_code=422, detail={"message": message})


# ---------------------------------------------------------------------------
# Pipelines and stages
# ---------------------------------------------------------------------------
async def list_pipelines(session: AsyncSession, *, account_id: int) -> list[CrmPipeline]:
    """The account's pipelines, creating the default one the first time."""
    rows = list(
        (
            await session.exec(
                select(CrmPipeline)
                .where(CrmPipeline.account_id == account_id)
                .order_by(col(CrmPipeline.is_default).desc(), col(CrmPipeline.id))
            )
        ).all()
    )
    if rows:
        return rows
    pipeline = CrmPipeline(account_id=account_id, is_default=True)
    session.add(pipeline)
    await session.flush()
    assert pipeline.id is not None
    _seed_default_stages(session, pipeline.id)
    await session.flush()
    return [pipeline]


async def get_pipeline(
    session: AsyncSession, *, account_id: int, pipeline_id: int
) -> CrmPipeline | None:
    return (
        await session.exec(
            select(CrmPipeline).where(
                CrmPipeline.id == pipeline_id, CrmPipeline.account_id == account_id
            )
        )
    ).first()


async def stages_for(session: AsyncSession, pipeline_ids: list[int]) -> list[CrmStage]:
    if not pipeline_ids:
        return []
    return list(
        (
            await session.exec(
                select(CrmStage)
                .where(col(CrmStage.pipeline_id).in_(pipeline_ids))
                .order_by(col(CrmStage.position), col(CrmStage.id))
            )
        ).all()
    )


def _clean_stages(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or not raw:
        raise _unprocessable("stages must be a non-empty array")
    cleaned: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise _unprocessable("each stage must be an object")
        kind = item.get("kind", STAGE_OPEN)
        if kind not in STAGE_KINDS:
            raise _unprocessable("stage kind is invalid")
        name = item.get("name")
        if name is not None and (not isinstance(name, str) or len(name) > 255):
            raise _unprocessable("stage name is invalid")
        if not item.get("id") and not (isinstance(name, str) and name.strip()):
            raise _unprocessable("Name can't be blank")
        probability = item.get("probability", 0)
        if not isinstance(probability, int) or not 0 <= probability <= 100:
            raise _unprocessable("stage probability must be between 0 and 100")
        cleaned.append(
            {
                "id": item.get("id"),
                "name": name.strip() if isinstance(name, str) and name.strip() else None,
                "kind": kind,
                "probability": probability,
            }
        )
    if not any(s["kind"] == STAGE_OPEN for s in cleaned):
        raise _unprocessable("a pipeline needs at least one open stage")
    return cleaned


def _seed_default_stages(session: AsyncSession, pipeline_id: int) -> None:
    for position, (code, kind, probability) in enumerate(DEFAULT_STAGES):
        session.add(
            CrmStage(
                pipeline_id=pipeline_id,
                code=code,
                kind=kind,
                probability=probability,
                position=position,
            )
        )


async def _sync_stages(
    session: AsyncSession, pipeline_id: int, wanted: list[dict[str, Any]]
) -> None:
    """Make the pipeline's stages ``wanted``, in that order: stages sent with
    an ``id`` are updated, new ones added, the others deleted — unless an
    opportunity is still in them."""
    current = {s.id: s for s in await stages_for(session, [pipeline_id])}
    keep_ids = {s["id"] for s in wanted if s["id"]}
    if keep_ids - set(current):
        raise _unprocessable("stage does not belong to this pipeline")
    for stage_id, stage in current.items():
        if stage_id in keep_ids:
            continue
        in_use = (
            await session.exec(
                select(CrmOpportunity.id).where(CrmOpportunity.stage_id == stage_id)
            )
        ).first()
        if in_use is not None:
            raise _unprocessable("stage has opportunities")
        await session.delete(stage)
    for position, item in enumerate(wanted):
        found = current.get(item["id"]) if item["id"] else None
        stage = found if found is not None else CrmStage(pipeline_id=pipeline_id)
        # A seeded stage keeps its translated name until someone types one.
        if item["name"] is not None or stage.code is None:
            stage.name = item["name"]
        stage.kind = item["kind"]
        stage.probability = item["probability"]
        stage.position = position
        session.add(stage)


async def save_pipeline(
    session: AsyncSession,
    *,
    account_id: int,
    pipeline: CrmPipeline | None,
    payload: dict[str, Any],
) -> CrmPipeline:
    """Create or edit a pipeline. ``stages``, when given, replaces the list
    (see :func:`_sync_stages`); a new pipeline without them gets the
    default stages."""
    creating = pipeline is None
    if creating:
        name = payload.get("name")
        if not isinstance(name, str) or not name.strip():
            raise _unprocessable("Name can't be blank")
        pipeline = CrmPipeline(account_id=account_id, name=name.strip())
        session.add(pipeline)
        await session.flush()
    assert pipeline is not None and pipeline.id is not None
    if not creating and "name" in payload:
        name = payload["name"]
        pipeline.name = name.strip() if isinstance(name, str) and name.strip() else None
    if "rotten_days" in payload:
        days = payload["rotten_days"]
        if not isinstance(days, int) or not 1 <= days <= 365:
            raise _unprocessable("rotten_days must be between 1 and 365")
        pipeline.rotten_days = days

    if creating and not payload.get("stages"):
        _seed_default_stages(session, pipeline.id)
    elif "stages" in payload:
        await _sync_stages(session, pipeline.id, _clean_stages(payload["stages"]))
    session.add(pipeline)
    await session.flush()
    await session.refresh(pipeline)
    return pipeline


async def delete_pipeline(session: AsyncSession, *, pipeline: CrmPipeline) -> None:
    if pipeline.is_default:
        raise _unprocessable("the default pipeline can't be deleted")
    await session.delete(pipeline)
    await session.flush()


# ---------------------------------------------------------------------------
# Opportunities
# ---------------------------------------------------------------------------
async def _stage_in_account(
    session: AsyncSession, *, account_id: int, stage_id: Any
) -> tuple[CrmStage, CrmPipeline]:
    if not isinstance(stage_id, int):
        raise _unprocessable("stage_id is required")
    stage = await session.get(CrmStage, stage_id)
    pipeline = await session.get(CrmPipeline, stage.pipeline_id) if stage else None
    if stage is None or pipeline is None or pipeline.account_id != account_id:
        raise _unprocessable("stage_id is invalid")
    return stage, pipeline


async def _check_reference(
    session: AsyncSession, model: Any, value: Any, account_id: int, field: str
) -> None:
    """``contact_id`` / ``product_id`` / ``conversation_id`` must be this
    account's."""
    if value is None:
        return
    row = await session.get(model, value) if isinstance(value, int) else None
    if row is None or getattr(row, "account_id", None) != account_id:
        raise _unprocessable(f"{field} is invalid")


async def _check_owner(session: AsyncSession, value: Any, account_id: int) -> None:
    if value is None:
        return
    member = (
        await session.exec(
            select(AccountUser.id).where(
                AccountUser.account_id == account_id, AccountUser.user_id == value
            )
        )
    ).first()
    if member is None:
        raise _unprocessable("owner_id is invalid")


def _parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise _unprocessable("expected_close_on is invalid") from exc


def _apply_stage(opportunity: CrmOpportunity, stage: CrmStage) -> None:
    moved = opportunity.stage_id != stage.id
    opportunity.stage_id = stage.id  # type: ignore[assignment]
    opportunity.pipeline_id = stage.pipeline_id
    if stage.kind == STAGE_OPEN:
        opportunity.closed_at = None
        opportunity.lost_reason = None if moved else opportunity.lost_reason
    elif opportunity.closed_at is None or moved:
        opportunity.closed_at = _now()
    if moved:
        opportunity.stage_changed_at = _now()


_EDITABLE = ("description", "currency", "lost_reason")


async def save_opportunity(
    session: AsyncSession,
    *,
    account_id: int,
    opportunity: CrmOpportunity | None,
    payload: dict[str, Any],
) -> CrmOpportunity:
    creating = opportunity is None
    if creating or "title" in payload:
        title = payload.get("title")
        if not isinstance(title, str) or not title.strip():
            raise _unprocessable("Title can't be blank")
        if len(title) > 255:
            raise _unprocessable("title exceeds 255 chars")
    if creating:
        if "stage_id" in payload:
            stage, _ = await _stage_in_account(
                session, account_id=account_id, stage_id=payload["stage_id"]
            )
        else:
            pipelines = await list_pipelines(session, account_id=account_id)
            first = (await stages_for(session, [pipelines[0].id]))[0]  # type: ignore[list-item]
            stage = first
        opportunity = CrmOpportunity(
            account_id=account_id,
            pipeline_id=stage.pipeline_id,
            stage_id=stage.id,
            title="",
            stage_changed_at=_now(),
        )
    assert opportunity is not None
    if "title" in payload:
        opportunity.title = payload["title"].strip()
    for field in _EDITABLE:
        if field in payload:
            setattr(opportunity, field, payload[field] or None)
    if "value" in payload:
        value = payload["value"]
        if value is not None and (not isinstance(value, int | float) or value < 0):
            raise _unprocessable("value is invalid")
        opportunity.value = value  # type: ignore[assignment]
    for field, model in (
        ("contact_id", Contact),
        ("product_id", Product),
        ("conversation_id", Conversation),
    ):
        if field in payload:
            await _check_reference(session, model, payload[field], account_id, field)
            setattr(opportunity, field, payload[field])
    if "owner_id" in payload:
        await _check_owner(session, payload["owner_id"], account_id)
        opportunity.owner_id = payload["owner_id"]
    if "expected_close_on" in payload:
        opportunity.expected_close_on = _parse_date(payload["expected_close_on"])
    if "position" in payload and isinstance(payload["position"], int | float):
        opportunity.position = float(payload["position"])
    if "stage_id" in payload and not creating:
        stage, _ = await _stage_in_account(
            session, account_id=account_id, stage_id=payload["stage_id"]
        )
        _apply_stage(opportunity, stage)
    elif creating:
        _apply_stage(opportunity, stage)
        opportunity.stage_changed_at = _now()
    session.add(opportunity)
    await session.flush()
    await session.refresh(opportunity)
    return opportunity


async def list_opportunities(
    session: AsyncSession,
    *,
    account_id: int,
    pipeline_id: int | None = None,
    contact_id: int | None = None,
    owner_id: int | None = None,
    status: str | None = None,
    q: str | None = None,
    company_id: int | None = None,
    limit: int = 500,
) -> list[CrmOpportunity]:
    stmt = select(CrmOpportunity).where(CrmOpportunity.account_id == account_id)
    if pipeline_id is not None:
        stmt = stmt.where(CrmOpportunity.pipeline_id == pipeline_id)
    if contact_id is not None:
        stmt = stmt.where(CrmOpportunity.contact_id == contact_id)
    if owner_id is not None:
        stmt = stmt.where(CrmOpportunity.owner_id == owner_id)
    if company_id is not None:
        # The company's opportunities are its people's.
        stmt = stmt.where(
            col(CrmOpportunity.contact_id).in_(
                select(Contact.id).where(
                    Contact.company_id == company_id, Contact.account_id == account_id
                )
            )
        )
    if status in STAGE_KINDS:
        stmt = stmt.join(CrmStage, col(CrmStage.id) == CrmOpportunity.stage_id).where(
            CrmStage.kind == status
        )
    if q and q.strip():
        stmt = stmt.where(col(CrmOpportunity.title).ilike(f"%{q.strip()}%"))
    stmt = stmt.order_by(col(CrmOpportunity.position), col(CrmOpportunity.id).desc())
    return list((await session.exec(stmt.limit(min(max(1, limit), 1000)))).all())


async def get_opportunity(
    session: AsyncSession, *, account_id: int, opportunity_id: int
) -> CrmOpportunity | None:
    return (
        await session.exec(
            select(CrmOpportunity).where(
                CrmOpportunity.id == opportunity_id,
                CrmOpportunity.account_id == account_id,
            )
        )
    ).first()


async def delete_opportunity(session: AsyncSession, *, opportunity: CrmOpportunity) -> None:
    await session.delete(opportunity)
    await session.flush()


__all__ = [
    "DEFAULT_STAGES",
    "delete_opportunity",
    "delete_pipeline",
    "get_opportunity",
    "get_pipeline",
    "list_opportunities",
    "list_pipelines",
    "save_opportunity",
    "save_pipeline",
    "stages_for",
]
