"""Execution models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field

from bud.models.common import BudModel


class ExecutionStatus(str, Enum):
    """Execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    # Uppercase variants from API
    PENDING_UPPER = "PENDING"
    RUNNING_UPPER = "RUNNING"
    COMPLETED_UPPER = "COMPLETED"
    FAILED_UPPER = "FAILED"
    CANCELLED_UPPER = "CANCELLED"


class StepStatus(str, Enum):
    """Step execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ExecutionStep(BudModel):
    """A single step in an execution."""

    id: str
    node_id: str
    name: str
    status: StepStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class ExecutionProgress(BudModel):
    """Execution progress information."""

    total_steps: int
    completed_steps: int
    failed_steps: int
    running_steps: int
    pending_steps: int
    percent_complete: float


class Execution(BudModel):
    """Execution resource."""

    # Primary ID (API returns 'id' for list/get, 'execution_id' for execute)
    id: str | None = None
    execution_id: str | None = None
    status: ExecutionStatus | str
    # Fields from our API
    pipeline_id: str | None = None
    pipeline_name: str | None = None
    # Execute API returns workflow_id/workflow_name instead
    workflow_id: str | None = None
    workflow_name: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    progress: ExecutionProgress | None = None
    steps: list[ExecutionStep] = Field(default_factory=list)
    started_at: datetime | str | None = None
    completed_at: datetime | str | None = None
    duration_ms: int | None = None
    error: str | None = None
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None
    # Additional fields from live API
    version: int | str | None = None
    pipeline_definition: dict[str, Any] | None = None
    initiator: str | None = None
    start_time: datetime | str | None = None
    end_time: datetime | str | None = None
    progress_percentage: str | float | None = None
    final_outputs: Any = None
    outputs: dict[str, Any] = Field(default_factory=dict)
    error_info: Any = None

    @property
    def effective_id(self) -> str:
        """Get the execution ID from either id or execution_id."""
        return self.id or self.execution_id or ""

    @property
    def effective_pipeline_id(self) -> str | None:
        """Get pipeline ID from either pipeline_id or workflow_id."""
        return self.pipeline_id or self.workflow_id

    @property
    def effective_pipeline_name(self) -> str | None:
        """Get pipeline name from available fields."""
        if self.pipeline_name:
            return self.pipeline_name
        if self.workflow_name:
            return self.workflow_name
        # Extract from pipeline_definition if available
        if self.pipeline_definition:
            return self.pipeline_definition.get("workflow_name")
        return None

    @property
    def effective_duration_ms(self) -> int | None:
        """Calculate duration in milliseconds from start/end times."""
        if self.duration_ms is not None:
            return self.duration_ms

        # Try to calculate from start_time and end_time
        start = self.start_time or self.started_at
        end = self.end_time or self.completed_at

        if start and end:
            from datetime import datetime

            # Parse timestamps if they're strings
            if isinstance(start, str):
                start = datetime.fromisoformat(start.replace("Z", "+00:00"))
            if isinstance(end, str):
                end = datetime.fromisoformat(end.replace("Z", "+00:00"))

            delta = end - start
            return int(delta.total_seconds() * 1000)

        return None

    @property
    def effective_duration_sec(self) -> str | None:
        """Calculate duration in seconds (formatted string)."""
        ms = self.effective_duration_ms
        if ms is not None:
            return f"{ms / 1000:.2f}"
        return None


class ExecutionCreate(BudModel):
    """Request to create/trigger an execution."""

    pipeline_id: str
    params: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)


class ExecutionEvent(BudModel):
    """An event during execution."""

    id: str
    execution_id: str
    step_id: str | None = None
    type: str
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime
