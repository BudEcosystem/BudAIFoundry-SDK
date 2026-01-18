"""Benchmark models for BudAI SDK."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Benchmark(BaseModel):
    """Benchmark result model."""

    id: str = Field(..., description="Benchmark ID")
    name: str = Field(..., description="Benchmark name")
    status: str = Field(..., description="Benchmark status")
    created_at: datetime | None = Field(None, description="Creation timestamp")
    updated_at: datetime | None = Field(None, description="Last update timestamp")
    results: dict[str, Any] | None = Field(None, description="Benchmark results")
    config: dict[str, Any] | None = Field(None, description="Benchmark configuration")


class BenchmarkList(BaseModel):
    """List of benchmarks with pagination."""

    items: list[Benchmark] = Field(default_factory=list, description="Benchmark items")
    total: int = Field(0, description="Total count")
    offset: int = Field(0, description="Current offset")
    limit: int = Field(20, description="Page size")


class BenchmarkFilters(BaseModel):
    """Available benchmark filter options."""

    statuses: list[str] = Field(default_factory=list, description="Available status values")
    types: list[str] = Field(default_factory=list, description="Available benchmark types")
