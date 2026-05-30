"""Idempotent seed: create a demo admin account for local UI testing.

Run from the repo root with the venv active:

    DATABASE_URL="postgresql+asyncpg://alostudio:alostudio@localhost:5433/alostudio" \
        python scripts/seed_demo_account.py

Outputs the email + password on success. Safe to re-run — if the user
already exists, it just prints the credentials.
"""

from __future__ import annotations

import asyncio
import os
import sys

from sqlmodel import select

from app.core.db import get_session_factory
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.users.models import User

EMAIL = "demo@example.com"
PASSWORD = "Password123!"


async def main() -> int:
    factory = get_session_factory()
    async with factory() as session:
        existing = (
            await session.exec(select(User).where(User.email == EMAIL))
        ).first()
        if existing is not None:
            print(f"User already exists: {EMAIL}")
            print(f"Password (unchanged): {PASSWORD}")
            return 0

        owner = await AccountBuilder(
            session,
            AccountBuilderParams(
                email=EMAIL,
                account_name="Demo Co",
                user_full_name="Demo Admin",
                user_password=PASSWORD,
                confirmed=True,
            ),
        ).perform()
        await session.commit()

        print(f"Created account {owner.account.id} for user {owner.user.id}")
        print(f"Email:    {EMAIL}")
        print(f"Password: {PASSWORD}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
