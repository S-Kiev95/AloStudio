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
  * ``GET    /companies``                  — filters: q, contact_id (its company)
  * ``POST   /companies``, ``GET|PATCH|DELETE /companies/{id}``
  * ``POST   /companies/{id}/contacts``    — ``{contact_id}`` joins it
  * ``DELETE /companies/{id}/contacts/{contact_id}``

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
from app.domains.contacts.models import Contact
from app.domains.crm import activities as act
from app.domains.crm import companies as comp
from app.domains.crm import origin as org
from app.domains.crm import service as svc
from app.domains.crm.models import CrmActivity, CrmCompany, CrmOpportunity, CrmPipeline
from app.domains.crm.presenters import (
    present_activities,
    present_company,
    present_company_contact,
    present_opportunities,
    present_pipeline,
)
from app.domains.crm.schemas import (
    ActivityBody,
    CompanyBody,
    CompanyContactBody,
    ContactOriginBody,
    OpportunityBody,
    PipelineBody,
)

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
    company_id: int | None = None,
) -> list[dict[str, Any]]:
    rows = await svc.list_opportunities(
        session,
        account_id=_account_id(ctx),
        pipeline_id=pipeline_id,
        contact_id=contact_id,
        owner_id=owner_id,
        status=status,
        q=q,
        company_id=company_id,
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



# ---------------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------------
async def _company(session: AsyncSession, ctx: AccountContext, company_id: int) -> CrmCompany:
    row = await comp.get_company(session, account_id=_account_id(ctx), company_id=company_id)
    if row is None:
        raise ChatwootHTTPException(status_code=404, detail=_NOT_FOUND)
    return row


async def _present_company(session: AsyncSession, company: CrmCompany) -> dict[str, Any]:
    assert company.id is not None
    counts = await comp.contact_counts(session, [company.id])
    return present_company(company, counts.get(company.id, 0))


@router.get("/companies")
async def index_companies(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    q: str | None = None,
    contact_id: int | None = None,
) -> list[dict[str, Any]]:
    rows = await comp.list_companies(
        session, account_id=_account_id(ctx), q=q, contact_id=contact_id
    )
    counts = await comp.contact_counts(session, [r.id for r in rows if r.id is not None])
    return [present_company(r, counts.get(r.id or 0, 0)) for r in rows]


@router.post("/companies")
async def create_company(
    body: CompanyBody,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    row = await comp.save_company(
        session,
        account_id=_account_id(ctx),
        company=None,
        payload=body.model_dump(exclude_unset=True),
    )
    return await _present_company(session, row)


@router.get("/companies/{company_id}")
async def show_company(
    company_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    company = await _company(session, ctx, company_id)
    body = await _present_company(session, company)
    body["contacts"] = [
        present_company_contact(c) for c in await comp.company_contacts(session, company)
    ]
    return body


@router.patch("/companies/{company_id}")
async def update_company(
    company_id: Annotated[int, Path()],
    body: CompanyBody,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    row = await comp.save_company(
        session,
        account_id=_account_id(ctx),
        company=await _company(session, ctx, company_id),
        payload=body.model_dump(exclude_unset=True),
    )
    return await _present_company(session, row)


@router.delete("/companies/{company_id}")
async def destroy_company(
    company_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    await comp.delete_company(session, company=await _company(session, ctx, company_id))
    return {}


@router.post("/companies/{company_id}/contacts")
async def add_company_contact(
    company_id: Annotated[int, Path()],
    body: CompanyContactBody,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    company = await _company(session, ctx, company_id)
    contact = await comp.set_contact_company(
        session, account_id=_account_id(ctx), contact_id=body.contact_id, company=company
    )
    return present_company_contact(contact)


@router.delete("/companies/{company_id}/contacts/{contact_id}")
async def remove_company_contact(
    company_id: Annotated[int, Path()],
    contact_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    company = await _company(session, ctx, company_id)
    members = {c.id for c in await comp.company_contacts(session, company)}
    if contact_id not in members:
        raise ChatwootHTTPException(status_code=404, detail=_NOT_FOUND)
    await comp.set_contact_company(
        session, account_id=_account_id(ctx), contact_id=contact_id, company=None
    )
    return {}


@router.put("/contacts/{contact_id}/origin")
async def set_contact_origin(
    contact_id: Annotated[int, Path()],
    body: ContactOriginBody,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Set (or clear, with ``source: null``) how a contact first came."""
    contact = await session.get(Contact, contact_id)
    if contact is None or contact.account_id != _account_id(ctx):
        raise ChatwootHTTPException(status_code=404, detail=_NOT_FOUND)
    try:
        org.set_origin(contact, source=body.source, channel=body.channel, detail=body.detail)
    except ValueError as exc:
        raise ChatwootHTTPException(status_code=422, detail={"message": str(exc)}) from exc
    session.add(contact)
    await session.flush()
    return {"origin": org.present_origin(contact)}


__all__ = ["router"]
