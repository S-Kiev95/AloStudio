"""Set a user's password, typed at the terminal.

    python scripts/set_user_password.py alguien@ejemplo.com

Exists so provisioning a login never puts a credential anywhere it can be
read later. The password is read with ``getpass`` — not a CLI argument, so
it stays out of shell history and out of ``ps`` — and only its bcrypt hash
is written. Nothing is printed but the outcome.

Also stamps ``confirmed_at`` when it is missing: a user created by a seed
script has never clicked a confirmation link, and without it the login
refuses a correct password, which reads as "the password did not work".
"""

from __future__ import annotations

import asyncio
import getpass
import sys
from datetime import UTC, datetime

from sqlmodel import select

import app.main  # noqa: F401  — closes the SQLAlchemy mapper registry
from app.core.db import get_session_factory
from app.core.security import hash_password
from app.domains.users.models import User

MIN_LENGTH = 8


async def main() -> int:
    if len(sys.argv) != 2:
        print("uso: python scripts/set_user_password.py <email>")
        return 2
    email = sys.argv[1].strip().lower()

    password = getpass.getpass("Contraseña nueva: ")
    if len(password) < MIN_LENGTH:
        print(f"!! muy corta (mínimo {MIN_LENGTH} caracteres)")
        return 1
    if password != getpass.getpass("Repetir: "):
        print("!! no coinciden")
        return 1

    async with get_session_factory()() as session:
        user = (
            await session.exec(select(User).where(User.email == email))
        ).first()
        if user is None:
            print(f"!! no existe el usuario {email}")
            return 1
        user.encrypted_password = hash_password(password)
        if user.confirmed_at is None:
            user.confirmed_at = datetime.now(UTC).replace(tzinfo=None)
            print("   (cuenta confirmada)")
        session.add(user)
        await session.commit()

    print(f"listo: contraseña actualizada para {email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
