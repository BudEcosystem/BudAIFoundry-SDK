"""Audit models for BudAI SDK."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AuditRecord(BaseModel):
    """Audit record model."""

    id: str = Field(..., description="Audit record ID")
    action: str = Field(..., description="Action performed")
    user_id: str | None = Field(None, description="User who performed the action")
    timestamp: datetime | None = Field(None, description="When the action occurred")
    details: dict[str, Any] | None = Field(None, description="Additional details")
    resource_type: str | None = Field(None, description="Type of resource affected")
    resource_id: str | None = Field(None, description="ID of resource affected")


class AuditList(BaseModel):
    """List of audit records with pagination."""

    items: list[AuditRecord] = Field(default_factory=list, description="Audit record items")
    total: int = Field(0, description="Total count")
    offset: int = Field(0, description="Current offset")
    limit: int = Field(20, description="Page size")
