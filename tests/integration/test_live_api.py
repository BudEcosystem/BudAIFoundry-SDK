"""Integration tests against live API.

These tests are skipped unless BUD_API_KEY is set.
"""

from __future__ import annotations

import os

import pytest

from bud import BudClient, Pipeline, Task

# Skip all tests in this module if no API key
pytestmark = pytest.mark.skipif(
    not os.getenv("BUD_API_KEY"),
    reason="BUD_API_KEY not set",
)


@pytest.fixture
def live_client() -> BudClient:
    """Create a client for live API testing."""
    return BudClient()


class TestLivePipelines:
    """Live pipeline tests."""

    def test_list_pipelines(self, live_client: BudClient) -> None:
        """Test listing pipelines from live API."""
        pipelines = live_client.pipelines.list()
        assert isinstance(pipelines, list)

    def test_pipeline_lifecycle(self, live_client: BudClient) -> None:
        """Test full pipeline lifecycle."""
        # Create
        with Pipeline("sdk-test-pipeline") as p:
            Task("step1", action="bud.noop")

        pipeline = live_client.pipelines.create(
            p.to_dag(),
            name="sdk-test-pipeline",
            description="Created by SDK integration test",
        )

        try:
            assert pipeline.id is not None
            assert pipeline.name == "sdk-test-pipeline"

            # Get
            fetched = live_client.pipelines.get(pipeline.id)
            assert fetched.id == pipeline.id

            # Update
            updated = live_client.pipelines.update(
                pipeline.id,
                description="Updated by SDK test",
            )
            assert updated.description == "Updated by SDK test"

        finally:
            # Cleanup
            live_client.pipelines.delete(pipeline.id)


class TestLiveExecutions:
    """Live execution tests."""

    def test_list_executions(self, live_client: BudClient) -> None:
        """Test listing executions from live API."""
        executions = live_client.executions.list()
        assert isinstance(executions, list)
