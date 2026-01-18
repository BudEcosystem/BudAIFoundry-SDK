"""Cluster models for BudAI SDK."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Cluster(BaseModel):
    """Cluster model."""

    id: str = Field(..., description="Cluster ID")
    name: str = Field(..., description="Cluster name")
    status: str = Field(..., description="Cluster status")
    node_count: int = Field(0, description="Number of nodes")
    created_at: datetime | None = Field(None, description="Creation timestamp")
    updated_at: datetime | None = Field(None, description="Last update timestamp")
    config: dict[str, Any] | None = Field(None, description="Cluster configuration")


class ClusterList(BaseModel):
    """List of clusters with pagination."""

    items: list[Cluster] = Field(default_factory=list, description="Cluster items")
    total: int = Field(0, description="Total count")
