"""Seed the demo account used by the Playwright e2e suite.

Creates (idempotently) an admin user demo@example.com / Password123!
on an account named "Demo Co" — the credentials + account name the
e2e helpers (frontend/tests/e2e/helpers.ts) assume.

Run:
    DATABASE_URL=postgresql+asyncpg://alostudio:alostudio@localhost:5433/alostudio \
        python -m scripts.seed_demo
"""

from __future__ import annotations

import asyncio
import os

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "Password123!"
DEMO_ACCOUNT = "Demo Co"


async def main() -> None:
    # Import inside main so the module is import-safe before app config loads.
    from app.domains.accounts.service import (
        AccountBuilder,
        AccountBuilderParams,
    )
    from app.domains.teams import models as _teams  # noqa: F401 (mapper)
    from app.domains.users.models import User

    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://alostudio:alostudio@localhost:5433/alostudio",
    )
    engine = create_async_engine(url)
    sm = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    try:
        async with sm() as session:
            existing = (
                await session.exec(
                    select(User).where(User.email == DEMO_EMAIL)
                )
            ).first()
            if existing is not None:
                print(f"[seed] {DEMO_EMAIL} already exists — nothing to do.")
                return
            owner = await AccountBuilder(
                session,
                AccountBuilderParams(
                    email=DEMO_EMAIL,
                    account_name=DEMO_ACCOUNT,
                    user_full_name="Demo Admin",
                    user_password=DEMO_PASSWORD,
                    confirmed=True,
                ),
            ).perform()
            await session.commit()
            print(
                f"[seed] created account_id={owner.account.id} "
                f"user_id={owner.user.id} ({DEMO_EMAIL} / {DEMO_PASSWORD})"
            )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
