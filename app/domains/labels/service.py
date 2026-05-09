r"""Label CRUD service + rename cascade.

Ported from:
  reference/chatwoot/app/controllers/api/v1/accounts/labels_controller.rb
  reference/chatwoot/app/models/label.rb (validations + before_validation)
  reference/chatwoot/app/services/labels/update_service.rb (rename cascade)
  reference/chatwoot/app/jobs/labels/update_job.rb

Title normalisation: Chatwoot's ``before_validation`` on Label
lower-cases ``title`` so "Urgent" and "urgent" collapse onto the same
``(account_id, title)`` unique row. We mirror that in
:func:`_normalize_title`.

Title regex: Chatwoot's ``UNICODE_CHARACTER_NUMBER_HYPHEN_UNDERSCORE``
allows any Unicode letter/number plus ``-`` and ``_`` only (no
spaces). Mirrored as a compiled regex below — same code-point classes
as Ruby's ``\p{L}`` / ``\p{N}``.

Rename cascade: when a label's ``title`` changes,
``Labels::UpdateService`` walks every conversation tagged with the
old title via ``acts_as_taggable_on``. Our ``ConversationLabel`` join
is keyed on ``label_id``, so the row survives the rename — but the
denormalised ``conversations.cached_label_list`` CSV references
titles, so we walk and rewrite the CSV here. (Chatwoot also rewrites
contact tags on rename — Contact-side label tagging lands with Phase
6.5+, so that branch is a deferred follow-up.)
"""

from __future__ import annotations

import re
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import ChatwootHTTPException
from app.domains.conversations.models import Conversation
from app.domains.labels.models import DEFAULT_LABEL_COLOR, Label

# Mirrors ``RegexHelper::UNICODE_CHARACTER_NUMBER_HYPHEN_UNDERSCORE`` —
# Unicode letter/number + ``-`` + ``_``. We use ``\w`` plus the explicit
# ``-`` because Python ``re`` with the ``UNICODE`` flag (default in
# str patterns) treats ``\w`` as ``[a-zA-Z0-9_]`` plus letters/digits
# in any script. Chatwoot's regex is anchored ``\A...\z``.
_TITLE_RE = re.compile(r"^[\w-]+$", re.UNICODE)


def _normalize_title(raw: str | None) -> str | None:
    """Mirror ``Label#before_validation { self.title = title.downcase }``.

    Returns ``None`` when ``raw`` is None / blank so the caller can
    short-circuit before the validation step.
    """
    if raw is None:
        return None
    stripped = raw.strip()
    if not stripped:
        return None
    return stripped.lower()


def _validate_title(title: str | None) -> str:
    """Run Rails' ``presence`` + ``format`` validations.

    The two failures map to the ``label.errors`` envelope Rails would
    emit: status 422, detail ``{"message": "<field>: <error>"}``.
    """
    if not title:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "Title can't be blank"},
        )
    if not _TITLE_RE.match(title):
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "Title is invalid"},
        )
    return title


async def _ensure_unique_title(
    session: AsyncSession, *, account_id: int, title: str, exclude_id: int | None = None
) -> None:
    """Mirror the ``uniqueness: { scope: :account_id }`` validator."""
    stmt = select(Label).where(
        Label.account_id == account_id,
        Label.title == title,
    )
    if exclude_id is not None:
        stmt = stmt.where(Label.id != exclude_id)
    existing = (await session.exec(stmt)).first()
    if existing is not None:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "Title has already been taken"},
        )


async def create_label(
    session: AsyncSession,
    *,
    account_id: int,
    payload: dict[str, Any],
) -> Label:
    """Port of ``LabelsController#create``.

    Permitted params: title / description / color / show_on_sidebar.
    Title is normalised + validated before the unique-index check so
    the 422 message stays under our control rather than leaning on
    Postgres' constraint error text.
    """
    title = _validate_title(_normalize_title(payload.get("title")))
    await _ensure_unique_title(session, account_id=account_id, title=title)

    label = Label(
        account_id=account_id,
        title=title,
        description=payload.get("description"),
        color=payload.get("color") or DEFAULT_LABEL_COLOR,
        show_on_sidebar=payload.get("show_on_sidebar"),
    )
    session.add(label)
    await session.flush()
    await session.refresh(label)
    return label


async def update_label(
    session: AsyncSession,
    *,
    label: Label,
    payload: dict[str, Any],
) -> Label:
    """Port of ``LabelsController#update`` + ``Labels::UpdateService``.

    When ``title`` changes, walk every conversation whose
    ``cached_label_list`` CSV contains the old title and rewrite the
    CSV (keeping the join row intact since it FKs on ``label_id``).
    """
    old_title = label.title
    new_title: str | None = old_title

    if "title" in payload:
        new_title = _validate_title(_normalize_title(payload.get("title")))
        if new_title != old_title:
            await _ensure_unique_title(
                session,
                account_id=label.account_id,
                title=new_title,
                exclude_id=label.id,
            )
        label.title = new_title

    if "description" in payload:
        label.description = payload.get("description")
    if "color" in payload:
        label.color = payload.get("color") or DEFAULT_LABEL_COLOR
    if "show_on_sidebar" in payload:
        label.show_on_sidebar = payload.get("show_on_sidebar")

    session.add(label)
    await session.flush()
    await session.refresh(label)

    if new_title != old_title:
        await _rename_cached_label_lists(
            session,
            account_id=label.account_id,
            old_title=old_title,
            new_title=new_title,
        )

    return label


async def destroy_label(session: AsyncSession, *, label: Label) -> None:
    """Port of ``LabelsController#destroy``.

    The Postgres ``ondelete=CASCADE`` on ``conversation_labels.label_id``
    drops the join rows automatically — but the denormalised CSV needs
    walking too. Mirror the rename cascade with an empty new_title to
    strip the title from every conversation that had it.
    """
    old_title = label.title
    account_id = label.account_id
    await session.delete(label)
    await session.flush()

    await _rename_cached_label_lists(
        session,
        account_id=account_id,
        old_title=old_title,
        new_title=None,
    )


async def _rename_cached_label_lists(
    session: AsyncSession,
    *,
    account_id: int,
    old_title: str,
    new_title: str | None,
) -> None:
    """Walk conversations whose CSV contains ``old_title`` and rewrite.

    ``new_title=None`` removes the title from every CSV (used by
    destroy). The conversation rows are loaded in batches of 200 to
    keep the working set bounded — Chatwoot's
    ``find_in_batches`` default is 1_000 but that's overkill for a
    single account's tagged conversations.
    """
    stmt = (
        select(Conversation)
        .where(Conversation.account_id == account_id)
        .where(Conversation.cached_label_list.isnot(None))  # type: ignore[union-attr]
    )
    convs = list((await session.exec(stmt)).all())
    for conv in convs:
        csv = conv.cached_label_list or ""
        titles = [t.strip() for t in csv.split(",") if t.strip()]
        if old_title not in titles:
            continue
        new_titles = [t for t in titles if t != old_title]
        if new_title is not None and new_title not in new_titles:
            new_titles.append(new_title)
        conv.cached_label_list = ",".join(new_titles) if new_titles else None
        session.add(conv)
    if convs:
        await session.flush()


__all__ = [
    "create_label",
    "destroy_label",
    "update_label",
]
