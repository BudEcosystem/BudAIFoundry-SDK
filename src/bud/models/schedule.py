"""Schedule models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field

from bud.models.common import BudModel


class ScheduleStatus(str, Enum):
    """Schedule status."""

    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"


class Schedule(BudModel):
    """Schedule resource."""

    id: str
    pipeline_id: str
    name: str
    description: str = ""
    cron: str
    timezone: str = "UTC"
    status: ScheduleStatus = ScheduleStatus.ACTIVE
    params: dict[str, Any] = Field(default_factory=dict)
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    last_execution_id: str | None = None
    run_count: int = 0
    created_at: datetime
    updated_at: datetime | None = None


class ScheduleCreate(BudModel):
    """Request to create a schedule."""

    pipeline_id: str
    name: str
    description: str = ""
    cron: str
    timezone: str = "UTC"
    params: dict[str, Any] = Field(default_factory=dict)


class ScheduleUpdate(BudModel):
    """Request to update a schedule."""

    name: str | None = None
    description: str | None = None
    cron: str | None = None
    timezone: str | None = None
    params: dict[str, Any] | None = None
