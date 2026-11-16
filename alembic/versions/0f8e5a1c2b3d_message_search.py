"""message search: Spanish full text, accents ignored, typos tolerated

F8, step 1. Searching old conversations used ``ILIKE '%q%'`` over every
message — a sequential scan that grows with the account, exact on accents
("envio" never finds "envío"), and that answers with *conversations*
rather than the message that matched.

Two indexes over the same normalised text:

* a ``tsvector`` with the ``spanish`` configuration, for words: stems, so
  "cuota" finds "cuotas", and ranks the results;
* a trigram index, for fragments and typos: "cuot", or "cuotsa".

Both read ``alo_search_text(content)`` — lower-cased, accents removed.
``unaccent`` itself is only ``STABLE`` (it depends on a dictionary that
could change), and Postgres refuses a non-``IMMUTABLE`` function in an
index; the wrapper names the dictionary explicitly and is declared
``IMMUTABLE``, which is the documented way to index unaccented text.

Created ``CONCURRENTLY``: on a busy installation ``messages`` is the
biggest table, and a plain ``CREATE INDEX`` would block every incoming
message for as long as the build takes.

Revision ID: 0f8e5a1c2b3d
Revises: f5a6b7c8d9e1
"""

from __future__ import annotations

from alembic import op

revision = "0f8e5a1c2b3d"
down_revision = "f5a6b7c8d9e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION alo_search_text(text) RETURNS text
        LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
        AS $$ SELECT lower(public.unaccent('public.unaccent'::regdictionary, $1)) $$
        """
    )
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_messages_search_tsv "
            "ON messages USING gin "
            "(to_tsvector('spanish'::regconfig, alo_search_text(content)))"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_messages_search_trgm "
            "ON messages USING gin (alo_search_text(content) gin_trgm_ops)"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_messages_search_trgm")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_messages_search_tsv")
    op.execute("DROP FUNCTION IF EXISTS alo_search_text(text)")
    # The extensions stay: another feature may already depend on them, and
    # dropping one that something else uses would fail or, worse, cascade.
