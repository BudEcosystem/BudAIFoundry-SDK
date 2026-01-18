"""Event models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field

from bud.models.common import BudModel


class EventType(str, Enum):
    """Event type."""

    PIPELINE_CREATED = "pipeline.created"
    PIPELINE_UPDATED = "pipeline.updated"
    PIPELINE_DELETED = "pipeline.deleted"
    EXECUTION_STARTED = "execution.started"
    EXECUTION_COMPLETED = "execution.completed"
    EXECUTION_FAILED = "execution.failed"
    EXECUTION_CANCELLED = "execution.cancelled"
    STEP_STARTED = "step.started"
    STEP_COMPLETED = "step.completed"
    STEP_FAILED = "step.failed"
    SCHEDULE_TRIGGERED = "schedule.triggered"
    WEBHOOK_TRIGGERED = "webhook.triggered"


class Event(BudModel):
    """Event resource."""

    id: str
    type: EventType
    source: str
    data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime


class EventTrigger(BudModel):
    """Event trigger configuration."""

    id: str
    pipeline_id: str
    name: str
    description: str = ""
    event_type: EventType
    filter: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    created_at: datetime
    updated_at: datetime | None = None


class EventTriggerCreate(BudModel):
    """Request to create an event trigger."""

    pipeline_id: str
    name: str
    description: str = ""
    event_type: EventType
    filter: dict[str, Any] = Field(default_factory=dict)
