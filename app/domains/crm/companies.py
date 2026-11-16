"""Companies (F11): organizations, and which contacts work there."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, update
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import ChatwootHTTPException
from app.domains.contacts.models import Contact
from app.domains.crm.models import CrmCompany

_FIELDS = ("website", "email", "phone", "address", "tax_id", "notes")


def _unprocessable(message: str) -> ChatwootHTTPException:
    return ChatwootHTTPException(status_code=422, detail={"message": message})


async def save_company(
    session: AsyncSession, *, account_id: int, company: CrmCompany | None, payload: dict[str, Any]
) -> CrmCompany:
    if company is None or "name" in payload:
        name = payload.get("name")
        if not isinstance(name, str) or not name.strip():
            raise _unprocessable("Name can't be blank")
        if len(name) > 255:
            raise _unprocessable("name exceeds 255 chars")
    if company is None:
        company = CrmCompany(account_id=account_id, name="")
    if "name" in payload:
        company.name = payload["name"].strip()
    for field in _FIELDS:
        if field in payload:
            value = payload[field]
            setattr(company, field, value.strip() if isinstance(value, str) and value.strip() else None)
    session.add(company)
    await session.flush()
    await session.refresh(company)
    return company


async def list_companies(
    session: AsyncSession,
    *,
    account_id: int,
    q: str | None = None,
    contact_id: int | None = None,
    limit: int = 200,
) -> list[CrmCompany]:
    stmt = select(CrmCompany).where(CrmCompany.account_id == account_id)
    if q and q.strip():
        stmt = stmt.where(col(CrmCompany.name).ilike(f"%{q.strip()}%"))
    if contact_id is not None:
        stmt = stmt.where(
            col(CrmCompany.id).in_(
                select(Contact.company_id).where(
                    Contact.id == contact_id, Contact.account_id == account_id
                )
            )
        )
    stmt = stmt.order_by(func.lower(CrmCompany.name), col(CrmCompany.id))
    return list((await session.exec(stmt.limit(min(max(1, limit), 1000)))).all())


async def contact_counts(session: AsyncSession, company_ids: list[int]) -> dict[int, int]:
    if not company_ids:
        return {}
    rows = (
        await session.exec(
            select(Contact.company_id, func.count(col(Contact.id)))
            .where(col(Contact.company_id).in_(company_ids))
            .group_by(col(Contact.company_id))
        )
    ).all()
    return {int(company_id): int(n) for company_id, n in rows if company_id is not None}


async def get_company(
    session: AsyncSession, *, account_id: int, company_id: int
) -> CrmCompany | None:
    return (
        await session.exec(
            select(CrmCompany).where(
                CrmCompany.id == company_id, CrmCompany.account_id == account_id
            )
        )
    ).first()


async def company_contacts(session: AsyncSession, company: CrmCompany) -> list[Contact]:
    return list(
        (
            await session.exec(
                select(Contact)
                .where(
                    Contact.company_id == company.id,
                    Contact.account_id == company.account_id,
                )
                .order_by(func.lower(func.coalesce(Contact.name, "")), col(Contact.id))
            )
        ).all()
    )


async def set_contact_company(
    session: AsyncSession, *, account_id: int, contact_id: int, company: CrmCompany | None
) -> Contact:
    """Put a contact in ``company`` (or take it out with ``None``)."""
    contact = await session.get(Contact, contact_id)
    if contact is None or contact.account_id != account_id:
        raise _unprocessable("contact_id is invalid")
    contact.company_id = company.id if company is not None else None
    session.add(contact)
    await session.flush()
    return contact


async def delete_company(session: AsyncSession, *, company: CrmCompany) -> None:
    # No foreign key behind contacts.company_id: clear it here.
    await session.exec(
        update(Contact)
        .where(col(Contact.company_id) == company.id)
        .values(company_id=None)
    )
    await session.delete(company)
    await session.flush()


__all__ = [
    "company_contacts",
    "contact_counts",
    "delete_company",
    "get_company",
    "list_companies",
    "save_company",
    "set_contact_company",
]
