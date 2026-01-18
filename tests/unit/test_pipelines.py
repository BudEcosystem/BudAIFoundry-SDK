"""Tests for pipeline operations."""

from __future__ import annotations

from typing import Any

import pytest
import respx
from httpx import Response

from bud.client import BudClient
from bud.models.pipeline import Pipeline


@respx.mock
def test_list_pipelines(
    client: BudClient,
    base_url: str,
    sample_pipeline: dict[str, Any],
) -> None:
    """Test listing pipelines."""
    respx.get(f"{base_url}/budpipeline").mock(
        return_value=Response(200, json={"items": [sample_pipeline]})
    )

    pipelines = client.pipelines.list()

    assert len(pipelines) == 1
    assert pipelines[0].id == "pipe-123"
    assert pipelines[0].name == "test-pipeline"


@respx.mock
def test_get_pipeline(
    client: BudClient,
    base_url: str,
    sample_pipeline: dict[str, Any],
) -> None:
    """Test getting a single pipeline."""
    respx.get(f"{base_url}/budpipeline/pipe-123").mock(
        return_value=Response(200, json=sample_pipeline)
    )

    pipeline = client.pipelines.get("pipe-123")

    assert pipeline.id == "pipe-123"
    assert pipeline.name == "test-pipeline"
    assert pipeline.version == 1


@respx.mock
def test_create_pipeline(
    client: BudClient,
    base_url: str,
    sample_pipeline: dict[str, Any],
) -> None:
    """Test creating a pipeline."""
    respx.post(f"{base_url}/budpipeline").mock(
        return_value=Response(201, json=sample_pipeline)
    )

    dag = {
        "nodes": [{"id": "n1", "type": "action", "action_id": "test"}],
        "edges": [],
    }
    pipeline = client.pipelines.create(dag, name="test-pipeline")

    assert pipeline.id == "pipe-123"


@respx.mock
def test_delete_pipeline(
    client: BudClient,
    base_url: str,
) -> None:
    """Test deleting a pipeline."""
    respx.delete(f"{base_url}/budpipeline/pipe-123").mock(
        return_value=Response(204)
    )

    # Should not raise
    client.pipelines.delete("pipe-123")


@respx.mock
def test_validate_pipeline(
    client: BudClient,
    base_url: str,
) -> None:
    """Test validating a pipeline."""
    respx.post(f"{base_url}/budpipeline/validate").mock(
        return_value=Response(200, json={"valid": True, "errors": [], "warnings": []})
    )

    dag = {"nodes": [], "edges": []}
    result = client.pipelines.validate(dag)

    assert result.valid is True
    assert len(result.errors) == 0
