"""Operación de la migración a EmbeddingGemma 2 (F9).

    python scripts/embeddings_gemma.py estado
    python scripts/embeddings_gemma.py backfill [--cuenta ID]
    python scripts/embeddings_gemma.py modelo ID openai|gemma

* ``estado``: por cuenta, con qué modelo lee, cuántos vectores locales
  faltan y qué reglas por similitud tienen un umbral propio de OpenAI
  (``max_distance``) sin su par para Gemma (``max_distance_gemma``). Esas
  reglas se revisan una por una antes de pasar la cuenta a Gemma; el valor
  de OpenAI nunca se convierte.
* ``backfill``: encola la tarea ARQ que completa los vectores que faltan
  (se puede cortar y volver a encolar).
* ``modelo``: con qué modelo responde una cuenta. Volver atrás es correrlo
  otra vez con ``openai``: mientras estén configurados los dos, cada
  guardado escribe ambos vectores.

Correr desde la raíz del repo, con el ``.venv`` de la app.
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import exists, func
from sqlmodel import select

import app.main  # noqa: F401  — closes the SQLAlchemy mapper registry
from app.core.config import get_settings
from app.core.db import get_session_factory
from app.core.embeddings import (
    EMBEDDING_MODELS,
    MODEL_GEMMA,
    READ_MODEL_KEY,
    gemma_enabled,
    read_model_from,
)
from app.domains.accounts.models import Account
from app.domains.instagram.autoreply_models import InstagramCommentReply
from app.domains.instagram.post_autoreply_models import InstagramPostAutoreply
from app.domains.portals.models import Article, ArticleEmbedding, Portal


async def estado() -> int:
    print(
        f"servicio local: {'configurado' if gemma_enabled() else 'NO configurado'}"
        f" · modelo por defecto: {get_settings().embedding_read_model}"
        f" · sombra: {'sí' if get_settings().embedding_shadow else 'no'}"
    )
    async with get_session_factory()() as session:
        accounts = (await session.exec(select(Account).order_by(Account.id))).all()
        for account in accounts:
            replies = (
                await session.exec(
                    select(
                        func.count(),
                        func.count(InstagramCommentReply.embedding_gemma),
                    ).where(InstagramCommentReply.account_id == account.id)
                )
            ).one()
            has_gemma_row = exists().where(
                ArticleEmbedding.article_id == Article.id,
                ArticleEmbedding.model == MODEL_GEMMA,
            )
            articles = (
                await session.exec(
                    select(func.count(), func.count().filter(has_gemma_row))
                    .select_from(Article)
                    .join(Portal, Portal.id == Article.portal_id)
                    .where(Portal.account_id == account.id)
                )
            ).one()
            print(
                f"\ncuenta {account.id} · {account.name} · lee con "
                f"{read_model_from(account.internal_attributes)}"
            )
            print(f"  respuestas preparadas: {replies[1]}/{replies[0]} con vector local")
            print(f"  artículos: {articles[1]}/{articles[0]} con vector local")
            rules = (
                await session.exec(
                    select(InstagramPostAutoreply)
                    .where(
                        InstagramPostAutoreply.account_id == account.id,
                        InstagramPostAutoreply.match_type == "semantic",
                        InstagramPostAutoreply.max_distance.is_not(None),  # type: ignore[union-attr]
                    )
                    .order_by(InstagramPostAutoreply.id)
                )
            ).all()
            for rule in rules:
                gemma = (
                    rule.max_distance_gemma
                    if rule.max_distance_gemma is not None
                    else "sin definir (usa 0.15)"
                )
                print(
                    f"  regla {rule.id} (publicación {rule.post_id}): "
                    f"OpenAI {rule.max_distance} · Gemma {gemma}  ← revisar"
                )
    return 0


async def backfill(account_id: int | None) -> int:
    if not gemma_enabled():
        print("!! falta EMBEDDINGS_SERVICE_URL en el .env")
        return 1
    from arq import create_pool
    from arq.connections import RedisSettings

    pool = await create_pool(RedisSettings.from_dsn(get_settings().arq_redis_url))
    try:
        job = await pool.enqueue_job("backfill_gemma_embeddings_task", account_id)
    finally:
        await pool.aclose()
    alcance = f"cuenta {account_id}" if account_id is not None else "todas las cuentas"
    print(f"encolado ({alcance}): {job.job_id if job else 'ya estaba en cola'}")
    return 0


async def modelo(account_id: int, model: str) -> int:
    if model == MODEL_GEMMA and not gemma_enabled():
        print("!! falta EMBEDDINGS_SERVICE_URL en el .env")
        return 1
    async with get_session_factory()() as session:
        account = await session.get(Account, account_id)
        if account is None:
            print(f"!! no existe la cuenta {account_id}")
            return 1
        before = read_model_from(account.internal_attributes)
        # Reassign (not mutate) so SQLAlchemy sees the JSONB change.
        account.internal_attributes = {
            **(account.internal_attributes or {}),
            READ_MODEL_KEY: model,
        }
        session.add(account)
        await session.commit()
    print(f"listo: cuenta {account_id} pasa de {before} a {model}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("estado")
    b = sub.add_parser("backfill")
    b.add_argument("--cuenta", type=int, default=None)
    m = sub.add_parser("modelo")
    m.add_argument("cuenta", type=int)
    m.add_argument("modelo", choices=EMBEDDING_MODELS)
    args = parser.parse_args()
    if args.cmd == "estado":
        return asyncio.run(estado())
    if args.cmd == "backfill":
        return asyncio.run(backfill(args.cuenta))
    return asyncio.run(modelo(args.cuenta, args.modelo))


if __name__ == "__main__":
    raise SystemExit(main())
