"""Widget-specific service helpers.

Ports the small bits of Chatwoot's widget that don't belong in a
controller: the ``build_contact_inbox_with_token`` helper that bootstraps
a fresh anonymous visitor + token, and the HMAC validator used by
``set_user``.

Anchors:
  reference/chatwoot/app/helpers/widget_helper.rb
  reference/chatwoot/app/builders/contact_inbox_with_contact_builder.rb
  reference/chatwoot/app/controllers/api/v1/widget/contacts_controller.rb
    (``valid_hmac?``)
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.widget_token import encode_widget_token
from app.domains.contacts.models import Contact, ContactInbox
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.inboxes.models import Inbox, WebWidget


@dataclass(slots=True)
class WidgetSession:
    """Bundle returned by :func:`build_contact_inbox_with_token`.

    Mirrors the Ruby tuple ``[contact_inbox, token]`` plus the resolved
    contact for caller convenience.
    """

    contact: Contact
    contact_inbox: ContactInbox
    token: str


def _anonymous_visitor_name() -> str:
    """Mirror Rails ``Haikunator.haikunate(1000)``.

    Chatwoot uses Haikunator for anonymous contact names so the
    dashboard renders something readable instead of a raw UUID. We
    use a simpler ``visitor-<hex>`` placeholder — the wire shape is
    just a string, the dashboard only ever displays it.
    """
    return f"visitor-{secrets.token_hex(4)}"


async def build_contact_inbox_with_token(
    session: AsyncSession,
    *,
    web_widget: WebWidget,
    inbox: Inbox,
) -> WidgetSession:
    """Mirror ``WidgetHelper#build_contact_inbox_with_token``.

    Creates a fresh anonymous Contact + ContactInbox and a JWT token
    encoding ``{source_id, inbox_id}``. The widget JS persists the
    token in localStorage and includes it on every subsequent request
    via the ``X-Auth-Token`` header.
    """
    if web_widget.account_id is None or inbox.id is None:
        raise RuntimeError(
            "build_contact_inbox_with_token requires a persisted "
            "WebWidget + Inbox"
        )
    contact = Contact(
        account_id=web_widget.account_id,
        name=_anonymous_visitor_name(),
    )
    session.add(contact)
    await session.flush()
    await session.refresh(contact)

    contact_inbox = await ContactInboxBuilder(
        session=session,
        contact=contact,
        inbox=inbox,
    ).perform()

    token = encode_widget_token(
        source_id=contact_inbox.source_id,
        inbox_id=inbox.id,
    )
    return WidgetSession(
        contact=contact, contact_inbox=contact_inbox, token=token
    )


async def find_contact_inbox_by_source(
    session: AsyncSession, *, inbox_id: int, source_id: str
) -> ContactInbox | None:
    """Convenience lookup used by the widget context dependency."""
    if not source_id:
        return None
    stmt = select(ContactInbox).where(
        ContactInbox.inbox_id == inbox_id,
        ContactInbox.source_id == source_id,
    )
    return (await session.exec(stmt)).first()


def valid_hmac(
    *, hmac_token: str, identifier: str, identifier_hash: str
) -> bool:
    """Mirror ``ContactsController#valid_hmac?``.

    HMAC-SHA256 of ``identifier`` with the per-widget ``hmac_token``,
    compared in constant time to the client-supplied ``identifier_hash``.
    Constant-time compare matters here — Rails uses Ruby's
    ``OpenSSL::HMAC.hexdigest`` whose return value flows into Ruby's
    plain ``==``, so technically Rails is timing-leaky. We harden ours
    a notch with :func:`hmac.compare_digest`.
    """
    if not (hmac_token and identifier and identifier_hash):
        return False
    digest = hmac.new(
        hmac_token.encode("utf-8"),
        identifier.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(digest, identifier_hash)


__all__ = [
    "WidgetSession",
    "build_contact_inbox_with_token",
    "find_contact_inbox_by_source",
    "valid_hmac",
]
