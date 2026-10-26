"""Import CRM data (customers, products, appointments) exported from Postiz.

Usage:
    PYTHONPATH=. python scripts/import_postiz_crm.py --account-id 1 --file export.json [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.core.db import dispose_engine, get_session_factory
from app.core.models_registry import import_all_models
from app.domains.appointments.importer import ImportStats, import_postiz_crm


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Importa clientes, productos y citas exportados del CRM de Postiz."
    )
    parser.add_argument(
        "--account-id",
        type=int,
        required=True,
        help="ID de la cuenta en AloStudio donde cargar los datos.",
    )
    parser.add_argument(
        "--file",
        type=Path,
        required=True,
        help="Ruta al archivo JSON exportado desde Postiz.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra qué crearía sin escribir en la base de datos.",
    )
    return parser


async def run_cli(
    *, account_id: int, file_path: Path, dry_run: bool = False
) -> ImportStats:
    import_all_models()
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    factory = get_session_factory()
    try:
        async with factory() as session:
            stats = await import_postiz_crm(
                session,
                account_id=account_id,
                data=payload,
                dry_run=dry_run,
                log=print,
            )
            if not dry_run:
                await session.commit()
    finally:
        await dispose_engine()

    prefix = "[dry-run] Resumen" if dry_run else "Importación completada"
    print(
        f"{prefix}: "
        f"contactos +{stats.contacts_created} (={stats.contacts_reused}), "
        f"notas +{stats.notes_created}, "
        f"etiquetas +{stats.labels_created}, "
        f"productos +{stats.products_created} (={stats.products_reused}), "
        f"citas +{stats.appointments_created} (={stats.appointments_reused})."
    )
    return stats


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    asyncio.run(
        run_cli(
            account_id=args.account_id,
            file_path=args.file,
            dry_run=args.dry_run,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
