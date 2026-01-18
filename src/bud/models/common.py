"""Common models shared across resources."""

from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class BudModel(BaseModel):
    """Base model for all BudAI models."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        use_enum_values=True,
    )


class Pagination(BudModel):
    """Pagination metadata."""

    total: int
    page: int
    per_page: int
    total_pages: int


class PaginatedResponse(BudModel, Generic[T]):
    """Paginated response wrapper."""

    items: list[T]
    pagination: Pagination


class TimestampMixin(BudModel):
    """Mixin for models with timestamps."""

    created_at: datetime
    updated_at: datetime | None = None
