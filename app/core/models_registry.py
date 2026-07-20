"""Import every domain's ORM models so SQLAlchemy's mapper registry is whole.

SQLModel resolves ``relationship()`` targets by *class name* at mapper-config
time, so a process that touches the DB without having imported every model
blows up on the first query with a misleading error::

    expression 'Account' failed to locate a name ('Account')

The web app gets this for free — ``app.main`` imports every router, which
transitively imports every model. Processes that skip the app (the ARQ
worker, Alembic, one-off scripts) do not, and used to keep hand-maintained
import lists that silently drifted as domains were added.

Discovery is dynamic on purpose: a new ``app/domains/<x>/models.py`` is picked
up with no edit here, which is the whole point — the drift *was* the bug.
"""

from __future__ import annotations

import importlib
import pkgutil

import app.domains


def import_all_models() -> list[str]:
    """Import every ``app.domains.*.models`` module.

    Returns the imported module names (handy for a startup log or a test
    that asserts the registry is non-empty). Domains without a ``models``
    module are skipped; an ImportError *inside* one propagates, so a genuinely
    broken model module still fails loudly instead of silently degrading the
    registry.
    """
    imported: list[str] = []
    for module_info in pkgutil.iter_modules(app.domains.__path__):
        if not module_info.ispkg:
            continue
        name = f"app.domains.{module_info.name}.models"
        try:
            importlib.import_module(name)
        except ModuleNotFoundError as exc:
            # Only tolerate "this domain has no models module". A missing
            # import *within* the module is a real error.
            if exc.name != name:
                raise
            continue
        imported.append(name)
    return imported


__all__ = ["import_all_models"]
