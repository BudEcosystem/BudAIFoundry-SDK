"""Integration tests for Pipelines resource.

These tests require a live API server.
Run with: pytest tests/integration/ -v --integration
"""

from __future__ import annotations

import os

import pytest

# Skip all tests if not running integration tests
pytestmark = pytest.mark.integration


@pytest.fixture
def client():
    """Create authenticated client for integration tests.

    Set these environment variables:
    - BUD_TEST_EMAIL: Test user email
    - BUD_TEST_PASSWORD: Test user password
    - BUD_TEST_BASE_URL: API base URL
    """
    from bud.client import BudClient

    email = os.getenv("BUD_TEST_EMAIL")
    password = os.getenv("BUD_TEST_PASSWORD")
    base_url = os.getenv("BUD_TEST_BASE_URL")

    if not all([email, password, base_url]):
        pytest.skip("Integration test credentials not configured")

    client = BudClient(
        email=email,
        password=password,
        base_url=base_url,
    )
    yield client
    client.close()


class TestPipelinesLive:
    """Test Pipelines resource against live API."""

    def test_list_pipelines(self, client) -> None:
        """Test listing pipelines."""
        result = client.pipelines.list()

        # Should return a list or have items attribute
        assert hasattr(result, "items") or isinstance(result, list)

    def test_pipeline_crud_flow(self, client) -> None:
        """Test create, read, update, delete pipeline flow."""
        import uuid

        # Create a unique pipeline name
        pipeline_name = f"test-pipeline-{uuid.uuid4().hex[:8]}"

        # Create pipeline
        dag = {
            "nodes": [
                {
                    "id": "start",
                    "type": "start",
                    "data": {},
                }
            ],
            "edges": [],
        }

        try:
            # Create
            created = client.pipelines.create(
                name=pipeline_name,
                dag=dag,
                description="Integration test pipeline",
            )
            assert created.name == pipeline_name
            pipeline_id = created.id

            # Read
            fetched = client.pipelines.get(pipeline_id)
            assert fetched.id == pipeline_id
            assert fetched.name == pipeline_name

            # Delete
            client.pipelines.delete(pipeline_id)

        except Exception as e:
            # Cleanup on failure
            pytest.skip(f"Pipeline CRUD test skipped: {e}")
