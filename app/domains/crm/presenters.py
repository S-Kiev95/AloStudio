"""Wire shapes for pipelines, stages and opportunities."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy.orm import lazyload
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.contacts.models import Contact
from app.domains.crm.models import (
    CrmActivity,
    CrmCompany,
    CrmOpportunity,
    CrmPipeline,
    CrmStage,
)
from app.domains.products.models import Product
from app.domains.users.models import User


def _ts(dt: datetime | None) -> int | None:
    return int(dt.timestamp()) if dt else None


def present_stage(stage: CrmStage) -> dict[str, Any]:
    return {
        "id": stage.id,
        "code": stage.code,
        "name": stage.name,
        "kind": stage.kind,
        "probability": stage.probability,
        "position": stage.position,
    }


def present_pipeline(pipeline: CrmPipeline, stages: Sequence[CrmStage]) -> dict[str, Any]:
    return {
        "id": pipeline.id,
        "name": pipeline.name,
        "is_default": pipeline.is_default,
        "rotten_days": pipeline.rotten_days,
        "stages": [present_stage(s) for s in stages if s.pipeline_id == pipeline.id],
    }


async def _by_id(session: AsyncSession, model: Any, ids: set[int]) -> dict[int, Any]:
    if not ids:
        return {}
    rows = (
        await session.exec(
            select(model).where(col(model.id).in_(ids)).options(lazyload("*"))
        )
    ).all()
    return {r.id: r for r in rows}


async def present_opportunities(
    session: AsyncSession, rows: Sequence[CrmOpportunity]
) -> list[dict[str, Any]]:
    """Batch-loads the contact, product and owner of each row (no N+1)."""
    contacts = await _by_id(session, Contact, {r.contact_id for r in rows if r.contact_id})
    products = await _by_id(session, Product, {r.product_id for r in rows if r.product_id})
    owners = await _by_id(session, User, {r.owner_id for r in rows if r.owner_id})
    out = []
    for r in rows:
        contact = contacts.get(r.contact_id) if r.contact_id else None
        product = products.get(r.product_id) if r.product_id else None
        owner = owners.get(r.owner_id) if r.owner_id else None
        out.append(
            {
                "id": r.id,
                "pipeline_id": r.pipeline_id,
                "stage_id": r.stage_id,
                "title": r.title,
                "description": r.description,
                "value": float(r.value) if r.value is not None else None,
                "currency": r.currency,
                "contact_id": r.contact_id,
                "product_id": r.product_id,
                "owner_id": r.owner_id,
                "conversation_id": r.conversation_id,
                "expected_close_on": (
                    r.expected_close_on.isoformat() if r.expected_close_on else None
                ),
                "closed_at": _ts(r.closed_at),
                "lost_reason": r.lost_reason,
                "position": r.position,
                "stage_changed_at": _ts(r.stage_changed_at),
                "created_at": _ts(r.created_at),
                "updated_at": _ts(r.updated_at),
                "contact": (
                    {
                        "id": contact.id,
                        "name": contact.name,
                        "avatar_url": getattr(contact, "avatar_url", None),
                    }
                    if contact
                    else None
                ),
                "product": {"id": product.id, "name": product.name} if product else None,
                "owner": (
                    {"id": owner.id, "name": owner.display_name or owner.name}
                    if owner
                    else None
                ),
            }
        )
    return out




async def present_activities(
    session: AsyncSession, rows: Sequence[CrmActivity]
) -> list[dict[str, Any]]:
    """Batch-loads the contact, opportunity and owner of each activity."""
    contacts = await _by_id(session, Contact, {r.contact_id for r in rows if r.contact_id})
    opportunities = await _by_id(
        session, CrmOpportunity, {r.opportunity_id for r in rows if r.opportunity_id}
    )
    owners = await _by_id(session, User, {r.owner_id for r in rows if r.owner_id})
    out = []
    for r in rows:
        contact = contacts.get(r.contact_id) if r.contact_id else None
        opportunity = opportunities.get(r.opportunity_id) if r.opportunity_id else None
        owner = owners.get(r.owner_id) if r.owner_id else None
        out.append(
            {
                "id": r.id,
                "kind": r.kind,
                "title": r.title,
                "description": r.description,
                "due_at": _ts(r.due_at),
                "done_at": _ts(r.done_at),
                "owner_id": r.owner_id,
                "contact_id": r.contact_id,
                "opportunity_id": r.opportunity_id,
                "created_at": _ts(r.created_at),
                "contact": (
                    {"id": contact.id, "name": contact.name, "avatar_url": contact.avatar_url}
                    if contact
                    else None
                ),
                "opportunity": (
                    {"id": opportunity.id, "title": opportunity.title} if opportunity else None
                ),
                "owner": (
                    {"id": owner.id, "name": owner.display_name or owner.name} if owner else None
                ),
            }
        )
    return out


def present_company(company: CrmCompany, contacts_count: int = 0) -> dict[str, Any]:
    return {
        "id": company.id,
        "name": company.name,
        "website": company.website,
        "email": company.email,
        "phone": company.phone,
        "address": company.address,
        "tax_id": company.tax_id,
        "notes": company.notes,
        "contacts_count": contacts_count,
        "created_at": _ts(company.created_at),
    }


def present_company_contact(contact: Contact) -> dict[str, Any]:
    return {
        "id": contact.id,
        "name": contact.name,
        "email": contact.email,
        "phone_number": contact.phone_number,
        "avatar_url": contact.avatar_url,
    }


__all__ = [
    "present_activities",
    "present_company",
    "present_company_contact",
    "present_opportunities",
    "present_pipeline",
    "present_stage",
]
