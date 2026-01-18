"""Webhook models."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from bud.models.common import BudModel


class Webhook(BudModel):
    """Webhook resource."""

    id: str
    pipeline_id: str
    name: str
    description: str = ""
    url: str
    is_active: bool = True
    secret_hash: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    last_triggered_at: datetime | None = None
    trigger_count: int = 0
    created_at: datetime
    updated_at: datetime | None = None


class WebhookCreate(BudModel):
    """Request to create a webhook."""

    pipeline_id: str
    name: str
    description: str = ""
    headers: dict[str, str] = Field(default_factory=dict)


class WebhookSecret(BudModel):
    """Webhook secret (returned only on create/rotate)."""

    webhook_id: str
    secret: str
    url: str


class WebhookTriggerResult(BudModel):
    """Result of triggering a webhook."""

    execution_id: str
    webhook_id: str
    triggered_at: datetime
