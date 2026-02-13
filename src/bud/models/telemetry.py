"""Pydantic models for the telemetry query API."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class FilterOperator(str, Enum):
    """Operators for filtering telemetry spans."""

    eq = "eq"
    neq = "neq"
    gt = "gt"
    gte = "gte"
    lt = "lt"
    lte = "lte"
    in_ = "in_"
    not_in = "not_in"
    like = "like"
    is_null = "is_null"
    is_not_null = "is_not_null"


class FilterCondition(BaseModel):
    """A single filter condition for telemetry queries."""

    field: str = Field(..., min_length=1, max_length=200)
    op: FilterOperator
    value: Any = None


class OrderBySpec(BaseModel):
    """Sort specification for telemetry queries."""

    field: str
    direction: Literal["asc", "desc"] = "desc"


class TelemetrySpanItem(BaseModel):
    """A single span item from telemetry query results."""

    timestamp: str
    trace_id: str
    span_id: str
    parent_span_id: str = ""
    trace_state: str = ""
    span_name: str
    span_kind: str = ""
    service_name: str = ""
    scope_name: str = ""
    scope_version: str = ""
    duration: int = 0
    status_code: str = ""
    status_message: str = ""
    child_count: int = 0
    children: list[TelemetrySpanItem] = Field(default_factory=list)
    attributes: dict[str, str] = Field(default_factory=dict)
    resource_attributes: dict[str, str] | None = None
    events: list[dict[str, Any]] | None = None
    links: list[dict[str, Any]] | None = None


class TelemetryQueryResponse(BaseModel):
    """Response model for telemetry queries.

    Maps to budapp's PaginatedSuccessResponse with page-based pagination.
    """

    object: str = "telemetry_query"
    data: list[TelemetrySpanItem] = Field(default_factory=list)
    page: int = 1
    limit: int = 10
    total_record: int = 0
    total_pages: int = 1
    message: str | None = None


class TelemetryErrorResponse(BaseModel):
    """Error response model from the telemetry query API.

    The SDK's HttpClient automatically detects non-2xx responses and raises
    the appropriate exception. This model is provided for reference.
    """

    object: str = "error"
    code: int = 500
    message: str | None = None
    type: str | None = "InternalServerError"
    param: str | None = None
