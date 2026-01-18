"""Pipeline models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field

from bud.models.common import BudModel


class DAGNodeType(str, Enum):
    """Type of DAG node."""

    ACTION = "action"
    CONDITION = "condition"
    PARALLEL = "parallel"
    WAIT = "wait"


class DAGNode(BudModel):
    """A node in the pipeline DAG."""

    id: str
    type: DAGNodeType
    action_id: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    condition: str | None = None
    timeout: int | None = None
    retry: dict[str, Any] | None = None


class PipelineDAG(BudModel):
    """Pipeline DAG definition."""

    nodes: list[DAGNode]
    edges: list[dict[str, str]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Pipeline(BudModel):
    """Pipeline resource."""

    id: str
    name: str
    description: str | None = None
    dag: PipelineDAG | dict[str, Any] | None = None
    version: int | str = 1  # API may return string
    status: str | None = None  # draft, published, etc.
    is_active: bool = True
    is_system: bool = False
    system_owned: bool = False  # Alias for is_system in API
    step_count: int | None = None
    execution_count: int | None = None
    user_id: str | None = None
    created_by: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None


class PipelineCreate(BudModel):
    """Request to create a pipeline."""

    name: str
    description: str = ""
    dag: dict[str, Any]
    tags: dict[str, str] = Field(default_factory=dict)


class PipelineUpdate(BudModel):
    """Request to update a pipeline."""

    name: str | None = None
    description: str | None = None
    dag: dict[str, Any] | None = None
    is_active: bool | None = None
    tags: dict[str, str] | None = None


class ValidationError(BudModel):
    """A single validation error."""

    path: str
    message: str
    code: str


class ValidationResult(BudModel):
    """Result of pipeline validation."""

    valid: bool
    # API returns errors/warnings as strings or objects depending on version
    errors: list[str] | list[ValidationError] = Field(default_factory=list)
    warnings: list[str] | list[ValidationError] = Field(default_factory=list)
    step_count: int | None = None
    has_cycles: bool | None = None
