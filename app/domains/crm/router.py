"""Sales pipeline endpoints (F11).

Route map, under ``/api/v1/accounts/{account_id}/crm``:
  * ``GET    /pipelines``                  — pipelines with their stages
  * ``POST   /pipelines``                  — admin
  * ``PATCH  /pipelines/{id}``             — admin (name, rotten_days, stages)
  * ``DELETE /pipelines/{id}``             — admin, not the default one
  * ``GET    /opportunities``              — filters: pipeline_id, contact_id,
    owner_id, status (open/won/lost), q
  * ``POST   /opportunities``
  * ``GET    /opportunities/{id}``
  * ``PATCH  /opportunities/{id}``         — includes moving it (stage_id)
  * ``DELETE /opportunities/{id}``
  * ``GET    /activities``                 — filters: owner_id, contact_id,
    opportunity_id, status (pending/overdue/done)
  * ``POST   /activities``
  * ``PATCH  /activities/{id}``            — ``done: true`` marks it done
  * ``DELETE /activities/{id}``

Selling is every agent's work: any member reads and edits opportunities;
shaping the pipeline is for administrators.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, account_context, require_admin
from app.core.errors import ChatwootHTTPException
from app.domains.crm import activities as act
from app.domains.crm import service as svc
from app.domains.crm.models import CrmActivity, CrmOpportunity, CrmPipeline
from app.domains.crm.presenters import (
    present_activities,
    present_opportunities,
    present_pipeline,
)
from app.domains.crm.schemas import ActivityBody, OpportunityBody, PipelineBody

router = APIRouter(prefix="/api/v1/accounts/{account_id}/crm", tags=["crm"])

_NOT_FOUND = {"error": "Resource could not be found"}


def _account_id(ctx: AccountContext) -> int:
    assert ctx.account.id is not None
    return ctx.account.id


async def _pipeline(session: AsyncSession, ctx: AccountContext, pipeline_id: int) -> CrmPipeline:
    row = await svc.get_pipeline(session, account_id=_account_id(ctx), pipeline_id=pipeline_id)
    if row is None:
        raise ChatwootHTTPException(status_code=404, detail=_NOT_FOUND)
    return row


async def _opportunity(
    session: AsyncSession, ctx: AccountContext, opportunity_id: int
) -> CrmOpportunity:
    row = await svc.get_opportunity(
        session, account_id=_account_id(ctx), opportunity_id=opportunity_id
    )
    if row is None:
        raise ChatwootHTTPException(status_code=404, detail=_NOT_FOUND)
    return row


async def _present_pipeline(session: AsyncSession, pipeline: CrmPipeline) -> dict[str, Any]:
    assert pipeline.id is not None
    return present_pipeline(pipeline, await svc.stages_for(session, [pipeline.id]))


# ---------------------------------------------------------------------------
# Pipelines
# ---------------------------------------------------------------------------
@router.get("/pipelines")
async def index_pipelines(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, Any]]:
    pipelines = await svc.list_pipelines(session, account_id=_account_id(ctx))
    stages = await svc.stages_for(session, [p.id for p in pipelines if p.id is not None])
    return [present_pipeline(p, stages) for p in pipelines]


@router.post("/pipelines")
async def create_pipeline(
    body: PipelineBody,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    pipeline = await svc.save_pipeline(
        session,
        account_id=_account_id(ctx),
        pipeline=None,
        payload=body.model_dump(exclude_unset=True),
    )
    return await _present_pipeline(session, pipeline)


@router.patch("/pipelines/{pipeline_id}")
async def update_pipeline(
    pipeline_id: Annotated[int, Path()],
    body: PipelineBody,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    pipeline = await _pipeline(session, ctx, pipeline_id)
    pipeline = await svc.save_pipeline(
        session,
        account_id=_account_id(ctx),
        pipeline=pipeline,
        payload=body.model_dump(exclude_unset=True),
    )
    return await _present_pipeline(session, pipeline)


@router.delete("/pipelines/{pipeline_id}")
async def destroy_pipeline(
    pipeline_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    await svc.delete_pipeline(session, pipeline=await _pipeline(session, ctx, pipeline_id))
    return {}


# ---------------------------------------------------------------------------
# Opportunities
# ---------------------------------------------------------------------------
@router.get("/opportunities")
async def index_opportunities(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    pipeline_id: int | None = None,
    contact_id: int | None = None,
    owner_id: int | None = None,
    status: str | None = None,
    q: str | None = None,
) -> list[dict[str, Any]]:
    rows = await svc.list_opportunities(
        session,
        account_id=_account_id(ctx),
        pipeline_id=pipeline_id,
        contact_id=contact_id,
        owner_id=owner_id,
        status=status,
        q=q,
    )
    return await present_opportunities(session, rows)


@router.post("/opportunities")
async def create_opportunity(
    body: OpportunityBody,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    payload = body.model_dump(exclude_unset=True)
    # Whoever creates it works it, unless they say otherwise.
    payload.setdefault("owner_id", ctx.user.id)
    row = await svc.save_opportunity(
        session, account_id=_account_id(ctx), opportunity=None, payload=payload
    )
    return (await present_opportunities(session, [row]))[0]


@router.get("/opportunities/{opportunity_id}")
async def show_opportunity(
    opportunity_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    row = await _opportunity(session, ctx, opportunity_id)
    return (await present_opportunities(session, [row]))[0]


@router.patch("/opportunities/{opportunity_id}")
async def update_opportunity(
    opportunity_id: Annotated[int, Path()],
    body: OpportunityBody,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    row = await _opportunity(session, ctx, opportunity_id)
    row = await svc.save_opportunity(
        session,
        account_id=_account_id(ctx),
        opportunity=row,
        payload=body.model_dump(exclude_unset=True),
    )
    return (await present_opportunities(session, [row]))[0]


@router.delete("/opportunities/{opportunity_id}")
async def destroy_opportunity(
    opportunity_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    await svc.delete_opportunity(
        session, opportunity=await _opportunity(session, ctx, opportunity_id)
    )
    return {}



# ---------------------------------------------------------------------------
# Activities and tasks
# ---------------------------------------------------------------------------
async def _activity(session: AsyncSession, ctx: AccountContext, activity_id: int) -> CrmActivity:
    row = await act.get_activity(session, account_id=_account_id(ctx), activity_id=activity_id)
    if row is None:
        raise ChatwootHTTPException(status_code=404, detail=_NOT_FOUND)
    return row


@router.get("/activities")
async def index_activities(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    owner_id: int | None = None,
    contact_id: int | None = None,
    opportunity_id: int | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    rows = await act.list_activities(
        session,
        account_id=_account_id(ctx),
        owner_id=owner_id,
        contact_id=contact_id,
        opportunity_id=opportunity_id,
        status=status,
    )
    return await present_activities(session, rows)


@router.post("/activities")
async def create_activity(
    body: ActivityBody,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    payload = body.model_dump(exclude_unset=True)
    payload.setdefault("owner_id", ctx.user.id)
    row = await act.save_activity(
        session, account_id=_account_id(ctx), activity=None, payload=payload, user_id=ctx.user.id
    )
    return (await present_activities(session, [row]))[0]


@router.patch("/activities/{activity_id}")
async def update_activity(
    activity_id: Annotated[int, Path()],
    body: ActivityBody,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    row = await act.save_activity(
        session,
        account_id=_account_id(ctx),
        activity=await _activity(session, ctx, activity_id),
        payload=body.model_dump(exclude_unset=True),
    )
    return (await present_activities(session, [row]))[0]


@router.delete("/activities/{activity_id}")
async def destroy_activity(
    activity_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    await act.delete_activity(session, activity=await _activity(session, ctx, activity_id))
    return {}


__all__ = ["router"]
