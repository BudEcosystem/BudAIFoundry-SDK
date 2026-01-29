"""Tests for execution operations."""

from __future__ import annotations

from typing import Any

import pytest
import respx
from httpx import Response

from bud.client import BudClient
from bud.exceptions import ExecutionError
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
    respx.post(f"{base_url}/budpipeline/pipe-123/execute").mock(
        return_value=Response(201, json=sample_execution)
    )

    execution = client.executions.create("pipe-123", params={"key": "value"})

    assert execution.pipeline_id == "pipe-123"


@respx.mock
def test_create_execution_with_callback_topics(
    client: BudClient,
    base_url: str,
    sample_execution: dict[str, Any],
) -> None:
    """Test creating execution with callback topics for Dapr pub/sub."""
    sample_execution["status"] = "pending"
    route = respx.post(f"{base_url}/budpipeline/pipe-123/execute").mock(
        return_value=Response(201, json=sample_execution)
    )

    execution = client.executions.create(
        "pipe-123",
        params={"key": "value"},
        callback_topics=["progress-topic", "completion-topic"],
        user_id="user-123",
        initiator="my-service",
    )

    assert execution.pipeline_id == "pipe-123"
    # Verify the request body contained the new fields
    request_body = route.calls[0].request.content
    import json

    body = json.loads(request_body)
    assert body["callback_topics"] == ["progress-topic", "completion-topic"]
    assert body["user_id"] == "user-123"
    assert body["initiator"] == "my-service"


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


@respx.mock
def test_run_ephemeral(
    client: BudClient,
    base_url: str,
) -> None:
    """Test running an ephemeral pipeline execution."""
    ephemeral_response = {
        "id": "exec-ephemeral-123",
        "pipeline_id": None,
        "pipeline_name": "ephemeral-test",
        "status": "pending",
        "params": {"input": "data"},
        "context": {},
        "progress": None,
        "steps": [],
        "started_at": None,
        "completed_at": None,
        "duration_ms": None,
        "error": None,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": None,
    }
    route = respx.post(f"{base_url}/budpipeline/run").mock(
        return_value=Response(201, json=ephemeral_response)
    )

    pipeline_definition = {
        "name": "ephemeral-test",
        "steps": [
            {"id": "step-1", "type": "action", "action_id": "bud.http.request"}
        ],
    }
    execution = client.executions.run_ephemeral(
        pipeline_definition,
        params={"input": "data"},
    )

    assert execution.id == "exec-ephemeral-123"
    assert execution.pipeline_id is None
    assert execution.status == ExecutionStatus.PENDING

    # Verify request body
    import json

    body = json.loads(route.calls[0].request.content)
    assert body["pipeline_definition"] == pipeline_definition
    assert body["params"] == {"input": "data"}


@respx.mock
def test_run_ephemeral_with_all_options(
    client: BudClient,
    base_url: str,
) -> None:
    """Test running ephemeral execution with all optional parameters."""
    ephemeral_response = {
        "id": "exec-ephemeral-456",
        "pipeline_id": None,
        "pipeline_name": "full-options-test",
        "status": "pending",
        "params": {"key": "value"},
        "context": {},
        "progress": None,
        "steps": [],
        "started_at": None,
        "completed_at": None,
        "duration_ms": None,
        "error": None,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": None,
    }
    route = respx.post(f"{base_url}/budpipeline/run").mock(
        return_value=Response(201, json=ephemeral_response)
    )

    pipeline_definition = {"name": "full-options-test", "steps": []}
    execution = client.executions.run_ephemeral(
        pipeline_definition,
        params={"key": "value"},
        callback_topics=["progress-topic"],
        user_id="user-789",
        initiator="test-service",
    )

    assert execution.id == "exec-ephemeral-456"

    # Verify all fields were sent in request
    import json

    body = json.loads(route.calls[0].request.content)
    assert body["pipeline_definition"] == pipeline_definition
    assert body["params"] == {"key": "value"}
    assert body["callback_topics"] == ["progress-topic"]
    assert body["user_id"] == "user-789"
    assert body["initiator"] == "test-service"


@respx.mock
def test_run_ephemeral_handles_error_response(
    client: BudClient,
    base_url: str,
) -> None:
    """Test that run_ephemeral raises ExecutionError on error response."""
    error_response = {
        "detail": {
            "error": "Invalid pipeline definition",
            "validation_errors": ["steps.0.id: Field required"],
        }
    }
    respx.post(f"{base_url}/budpipeline/run").mock(
        return_value=Response(200, json=error_response)
    )

    with pytest.raises(ExecutionError) as exc_info:
        client.executions.run_ephemeral(
            pipeline_definition={"name": "bad-pipeline", "steps": [{"name": "step1"}]},
        )

    assert "Failed to run ephemeral pipeline" in str(exc_info.value)
