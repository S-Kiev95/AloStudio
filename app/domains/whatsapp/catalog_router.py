"""Products from the Meta catalogue in WhatsApp chats (F5 + F11):

  * ``GET  /api/v1/accounts/{id}/whatsapp/catalog/products`` — products an
    agent can send (in the catalogue and accepted by Meta).
  * ``POST /api/v1/accounts/{id}/conversations/{display_id}/whatsapp/products``
    — send one or several of them in the conversation.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, ConfigDict
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, account_context
from app.core.errors import ChatwootHTTPException
from app.domains.conversations.presenters import present_message_create
from app.domains.conversations.router import (
    _load_conversation_by_display_id,
    _whatsapp_window_open,
)
from app.domains.conversations.service import MessageBuilderParams, create_message
from app.domains.inboxes.models import (
    CHANNEL_TYPE_WHATSAPP,
    WHATSAPP_PROVIDER_CLOUD,
    WhatsappChannel,
)
from app.domains.whatsapp.catalog import (
    build_products_message,
    catalog_id_for,
    present_product,
    sendable_products,
)

router = APIRouter(prefix="/api/v1/accounts/{account_id}", tags=["whatsapp-catalog"])


class SendProductsBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    product_ids: list[int]
    body: str | None = None
    header: str | None = None


def _unprocessable(message: str) -> ChatwootHTTPException:
    return ChatwootHTTPException(status_code=422, detail={"message": message})


@router.get("/whatsapp/catalog/products")
async def catalog_products_endpoint(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    return {
        "catalog_id": await catalog_id_for(session, ctx.account.id),
        "products": [present_product(p) for p in await sendable_products(session, ctx.account.id)],
    }


@router.post("/conversations/{display_id}/whatsapp/products")
async def send_products_endpoint(
    display_id: Annotated[int, Path()],
    payload: SendProductsBody,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    conv = await _load_conversation_by_display_id(session, ctx=ctx, display_id=display_id)
    inbox = conv.inbox
    if inbox is None or inbox.channel_type != CHANNEL_TYPE_WHATSAPP:
        raise _unprocessable("Los productos se mandan solo en conversaciones de WhatsApp.")
    channel = await session.get(WhatsappChannel, inbox.channel_id)
    if channel is None or channel.provider != WHATSAPP_PROVIDER_CLOUD:
        raise _unprocessable("Los productos se mandan solo por WhatsApp Cloud.")
    if not await _whatsapp_window_open(session, conv):
        raise _unprocessable(
            "Pasaron 24 h desde el último mensaje del contacto: mandá una plantilla."
        )
    content, attrs = await build_products_message(
        session,
        account_id=ctx.account.id,
        product_ids=payload.product_ids,
        body=payload.body,
        header=payload.header,
    )
    msg = await create_message(
        session,
        conversation=conv,
        params=MessageBuilderParams(
            content=content,
            message_type="outgoing",
            content_attributes=attrs,
        ),
        user_id=ctx.user.id,
    )
    body = present_message_create(msg, echo_id=None)
    await session.commit()
    return body


__all__ = ["router"]
