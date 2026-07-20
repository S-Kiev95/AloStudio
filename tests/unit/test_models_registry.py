"""The ORM mapper registry must be complete outside the web app.

SQLModel resolves ``relationship()`` targets by class name at mapper-config
time. A process that touches the DB without importing every model dies with
``expression 'Account' failed to locate a name`` — which is exactly how the
ARQ worker silently failed every job (Instagram posts sat in ``pending``).
"""

from __future__ import annotations

from pathlib import Path

from app.core.models_registry import import_all_models


def test_imports_every_domain_models_module():
    """Discovery must cover the filesystem — no hand-maintained list to
    drift out of date."""
    imported = set(import_all_models())
    domains_dir = Path(__file__).resolve().parents[2] / "app" / "domains"
    on_disk = {
        f"app.domains.{p.parent.name}.models"
        for p in domains_dir.glob("*/models.py")
    }
    assert on_disk, "no domain models found — bad test path?"
    assert on_disk <= imported


def test_mappers_configure_after_import():
    """The real assertion: with every model imported, SQLAlchemy can resolve
    the relationship graph. This is what the worker needs before any query."""
    from sqlalchemy.orm import configure_mappers

    import_all_models()
    configure_mappers()  # raises InvalidRequestError if a target is missing


def test_is_idempotent():
    """Called from both the worker entrypoint and Alembic — a second call
    must be a no-op, not a re-import storm."""
    assert set(import_all_models()) == set(import_all_models())
