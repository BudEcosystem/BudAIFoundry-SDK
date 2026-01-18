"""Tests for execution operations."""

from __future__ import annotations

from typing import Any

import pytest
import respx
from httpx import Response

from bud.client import BudClient
from bud.models.execution import ExecutionStatus


@respx.mock
def test_list_executions(
    client: BudClient,
    base_url: str,
    sample_execution: dict[str, Any],
) -> None:
    """Test listing executions."""
    respx.get(f"{base_url}/budpipeline/executions").mock(
        return_value=Response(200, json={"items": [sample_execution]})
    )

    executions = client.executions.list()

    assert len(executions) == 1
    assert executions[0].id == "exec-456"
    assert executions[0].status == ExecutionStatus.COMPLETED


@respx.mock
def test_get_execution(
    client: BudClient,
    base_url: str,
    sample_execution: dict[str, Any],
) -> None:
    """Test getting a single execution."""
    respx.get(f"{base_url}/budpipeline/executions/exec-456").mock(
        return_value=Response(200, json=sample_execution)
    )

    execution = client.executions.get("exec-456")

    assert execution.id == "exec-456"
    assert execution.pipeline_id == "pipe-123"
    assert execution.status == ExecutionStatus.COMPLETED


@respx.mock
def test_create_execution(
    client: BudClient,
    base_url: str,
    sample_execution: dict[str, Any],
) -> None:
    """Test creating/triggering an execution."""
    sample_execution["status"] = "pending"
    respx.post(f"{base_url}/budpipeline/executions").mock(
        return_value=Response(201, json=sample_execution)
    )

    execution = client.executions.create("pipe-123", params={"key": "value"})

    assert execution.pipeline_id == "pipe-123"


@respx.mock
def test_cancel_execution(
    client: BudClient,
    base_url: str,
    sample_execution: dict[str, Any],
) -> None:
    """Test cancelling an execution."""
    sample_execution["status"] = "cancelled"
    respx.post(f"{base_url}/budpipeline/executions/exec-456/cancel").mock(
        return_value=Response(200, json=sample_execution)
    )

    execution = client.executions.cancel("exec-456")

    assert execution.status == ExecutionStatus.CANCELLED


@respx.mock
def test_get_execution_progress(
    client: BudClient,
    base_url: str,
) -> None:
    """Test getting execution progress."""
    respx.get(f"{base_url}/budpipeline/executions/exec-456/progress").mock(
        return_value=Response(
            200,
            json={
                "total_steps": 5,
                "completed_steps": 3,
                "failed_steps": 0,
                "running_steps": 1,
                "pending_steps": 1,
                "percent_complete": 60.0,
            },
        )
    )

    progress = client.executions.get_progress("exec-456")

    assert progress.total_steps == 5
    assert progress.completed_steps == 3
    assert progress.percent_complete == 60.0
