"""Create a self-contained account to show the product from.

    python scripts/provision_demo_tenant.py --name "Demo Cliente" --user cliente@ejemplo.com

Not ``seed_demo_account.py``: that one exists for local UI work and bakes
in a fixed password, which is exactly what must not happen on a host
anyone can reach.

A separate account, not a separate view of an existing one: AloStudio is
multi-tenant, so a prospect logging in here sees only what was seeded for
them. Showing the product from the account that also holds real traffic
would put someone else's conversations in front of them.

Creates the account and the login, then leaves the data to
``seed_reports_demo.py --account <id>`` — that script already knows how to
build a plausible history, and duplicating it here would mean two things
to keep in step.

Deliberately does NOT set a password. It writes an unusable hash and
prints the one command that sets a real one, so the credential is typed by
whoever owns it and never passes through a script argument, a log, or a
transcript.

Re-running with the same name and email is a no-op, so it is safe to use
while getting a demo ready.
"""

from __future__ import annotations

import asyncio
import sys

from sqlmodel import select

import app.main  # noqa: F401  — closes the SQLAlchemy mapper registry
from app.core.db import get_session_factory
from app.core.tokens import base58_token
from app.domains.accounts.models import Account
from app.domains.users.models import AccessToken, AccountUser, User

# Long enough to be a valid column value, not a bcrypt hash, so it cannot
# match any password — the account is unusable until someone sets one.
UNUSABLE = "!" * 24

ROLE_ADMINISTRATOR = 1
ROLE_AGENT = 0


def _arg(flag: str, default: str) -> str:
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


async def main() -> int:
    name = _arg("--name", "Demo Cliente")
    email = _arg("--user", "").strip().lower()
    full_name = _arg("--full-name", "Cliente Demo")
    # Agent by default: a prospect should be able to look at everything
    # without being able to rewire the account they are being shown.
    role = ROLE_ADMINISTRATOR if "--admin" in sys.argv else ROLE_AGENT

    if not email:
        print("uso: provision_demo_tenant.py --name <cuenta> --user <email> [--admin]")
        return 2

    async with get_session_factory()() as session:
        account = (
            await session.exec(select(Account).where(Account.name == name))
        ).first()
        if account is None:
            account = Account(name=name)
            session.add(account)
            await session.flush()
            print(f"cuenta creada: {name!r} (id={account.id})")
        else:
            print(f"cuenta ya existía: {name!r} (id={account.id})")

        user = (
            await session.exec(select(User).where(User.email == email))
        ).first()
        if user is None:
            user = User(
                name=full_name,
                display_name=full_name.split()[0],
                email=email,
                uid=email,
                provider="email",
                encrypted_password=UNUSABLE,
            )
            session.add(user)
            await session.flush()
            print(f"usuario creado: {email} (id={user.id})")
        else:
            print(f"usuario ya existía: {email} (id={user.id})")

        # Every user needs a personal API token. Sign-in refuses to
        # complete without one — the password verifies, then the handler
        # 500s on a missing token, which surfaced as a login that simply
        # would not work. AccountBuilder mints it; creating a user by hand
        # has to as well.
        token = (
            await session.exec(
                select(AccessToken).where(
                    AccessToken.owner_type == "User",
                    AccessToken.owner_id == user.id,
                )
            )
        ).first()
        if token is None:
            session.add(
                AccessToken(
                    owner_type="User",
                    owner_id=user.id,
                    token=base58_token(24),
                )
            )
            print("token de API creado")

        link = (
            await session.exec(
                select(AccountUser).where(
                    AccountUser.account_id == account.id,
                    AccountUser.user_id == user.id,
                )
            )
        ).first()
        if link is None:
            session.add(
                AccountUser(
                    account_id=account.id, user_id=user.id, role=role
                )
            )
            print(f"vinculado a la cuenta como {'admin' if role else 'agente'}")

        await session.commit()
        account_id = account.id

    print()
    print("Falta la contraseña — la ponés vos, no queda escrita en ningún lado:")
    print(f"    python scripts/set_user_password.py {email}")
    print()
    print("Y para llenarla con datos de demostración:")
    print(f"    python scripts/seed_reports_demo.py --account {account_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
