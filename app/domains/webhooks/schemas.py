"""Pydantic schemas for Webhook CRUD."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class WebhookBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    inbox_id: int | None = None
    name: str | None = None
    url: str | None = None
    subscriptions: list[str] | None = None


class WebhookEnvelope(BaseModel):
    """Top-level wrapper — mirrors ``params.require(:webhook)``."""

    model_config = ConfigDict(extra="ignore")

    webhook: WebhookBody


__all__ = ["WebhookBody", "WebhookEnvelope"]
