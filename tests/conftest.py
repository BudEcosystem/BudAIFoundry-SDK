"""Pytest configuration and fixtures."""

from __future__ import annotations

from typing import Any, Generator
from unittest.mock import MagicMock

import pytest
import respx
from httpx import Response

from bud.client import AsyncBudClient, BudClient


@pytest.fixture
def api_key() -> str:
    """Test API key."""
    return "test-api-key-12345"


@pytest.fixture
def base_url() -> str:
    """Test API base URL."""
    return "https://api.test.bud.io"


@pytest.fixture
def mock_api(base_url: str) -> Generator[respx.MockRouter, None, None]:
    """Mock API router."""
    with respx.mock(base_url=base_url, assert_all_called=False) as router:
        yield router


@pytest.fixture
def client(api_key: str, base_url: str) -> Generator[BudClient, None, None]:
    """Create a test BudClient."""
    c = BudClient(api_key=api_key, base_url=base_url)
    yield c
    c.close()


@pytest.fixture
async def async_client(api_key: str, base_url: str) -> AsyncBudClient:
    """Create a test AsyncBudClient."""
    return AsyncBudClient(api_key=api_key, base_url=base_url)


# Sample response data
@pytest.fixture
def sample_pipeline() -> dict[str, Any]:
    """Sample pipeline response."""
    return {
        "id": "pipe-123",
        "name": "test-pipeline",
        "description": "A test pipeline",
        "dag": {
            "nodes": [
                {
                    "id": "node-1",
                    "type": "action",
                    "action_id": "bud.http.request",
                    "config": {},
                    "depends_on": [],
                }
            ],
            "edges": [],
            "metadata": {},
        },
        "version": 1,
        "is_active": True,
        "is_system": False,
        "tags": {},
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": None,
    }


@pytest.fixture
def sample_execution() -> dict[str, Any]:
    """Sample execution response."""
    return {
        "id": "exec-456",
        "pipeline_id": "pipe-123",
        "pipeline_name": "test-pipeline",
        "status": "completed",
        "params": {"key": "value"},
        "context": {},
        "progress": {
            "total_steps": 3,
            "completed_steps": 3,
            "failed_steps": 0,
            "running_steps": 0,
            "pending_steps": 0,
            "percent_complete": 100.0,
        },
        "steps": [],
        "started_at": "2024-01-01T00:00:00Z",
        "completed_at": "2024-01-01T00:01:00Z",
        "duration_ms": 60000,
        "error": None,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:01:00Z",
    }


@pytest.fixture
def sample_schedule() -> dict[str, Any]:
    """Sample schedule response."""
    return {
        "id": "sched-789",
        "pipeline_id": "pipe-123",
        "name": "daily-run",
        "description": "Run daily at midnight",
        "cron": "0 0 * * *",
        "timezone": "UTC",
        "status": "active",
        "params": {},
        "next_run_at": "2024-01-02T00:00:00Z",
        "last_run_at": None,
        "last_execution_id": None,
        "run_count": 0,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": None,
    }
