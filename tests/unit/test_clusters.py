"""Tests for Clusters resource."""

from __future__ import annotations

import httpx
import respx

from bud._http import HttpClient
from bud.auth import APIKeyAuth
from bud.resources.clusters import Clusters


class TestClustersResource:
    """Test Clusters resource methods."""

    @respx.mock
    def test_clusters_list(self) -> None:
        """Clusters should list all clusters."""
        respx.get("https://api.example.com/clusters/clusters").mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "cluster-1",
                            "name": "Production",
                            "status": "running",
                            "node_count": 3,
                        },
                        {
                            "id": "cluster-2",
                            "name": "Staging",
                            "status": "running",
                            "node_count": 1,
                        },
                    ],
                    "total": 2,
                },
            )
        )

        auth = APIKeyAuth(api_key="test-key")
        http = HttpClient(base_url="https://api.example.com", auth=auth)
        clusters = Clusters(http)

        result = clusters.list()

        assert len(result.items) == 2
        assert result.items[0].id == "cluster-1"
        assert result.items[0].name == "Production"

    @respx.mock
    def test_clusters_get(self) -> None:
        """Clusters should get a single cluster."""
        respx.get("https://api.example.com/clusters/cluster-1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "cluster-1",
                    "name": "Production",
                    "status": "running",
                    "node_count": 3,
                    "created_at": "2024-01-01T00:00:00Z",
                },
            )
        )

        auth = APIKeyAuth(api_key="test-key")
        http = HttpClient(base_url="https://api.example.com", auth=auth)
        clusters = Clusters(http)

        result = clusters.get("cluster-1")

        assert result.id == "cluster-1"
        assert result.name == "Production"
        assert result.node_count == 3

    @respx.mock
    def test_clusters_create(self) -> None:
        """Clusters should create a new cluster."""
        respx.post("https://api.example.com/clusters/clusters").mock(
            return_value=httpx.Response(
                201,
                json={
                    "id": "cluster-new",
                    "name": "New Cluster",
                    "status": "provisioning",
                    "node_count": 2,
                },
            )
        )

        auth = APIKeyAuth(api_key="test-key")
        http = HttpClient(base_url="https://api.example.com", auth=auth)
        clusters = Clusters(http)

        result = clusters.create(
            name="New Cluster",
            node_count=2,
            config={"region": "us-east-1"},
        )

        assert result.id == "cluster-new"
        assert result.name == "New Cluster"
        assert result.status == "provisioning"

    @respx.mock
    def test_clusters_update(self) -> None:
        """Clusters should update a cluster."""
        respx.patch("https://api.example.com/clusters/cluster-1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "cluster-1",
                    "name": "Updated Cluster",
                    "status": "running",
                    "node_count": 5,
                },
            )
        )

        auth = APIKeyAuth(api_key="test-key")
        http = HttpClient(base_url="https://api.example.com", auth=auth)
        clusters = Clusters(http)

        result = clusters.update("cluster-1", node_count=5, name="Updated Cluster")

        assert result.name == "Updated Cluster"
        assert result.node_count == 5

    @respx.mock
    def test_clusters_delete(self) -> None:
        """Clusters should delete a cluster."""
        respx.post("https://api.example.com/clusters/cluster-1/delete-workflow").mock(
            return_value=httpx.Response(204)
        )

        auth = APIKeyAuth(api_key="test-key")
        http = HttpClient(base_url="https://api.example.com", auth=auth)
        clusters = Clusters(http)

        # Should not raise
        clusters.delete("cluster-1")

    @respx.mock
    def test_clusters_get_endpoints(self) -> None:
        """Clusters should get cluster endpoints."""
        respx.get("https://api.example.com/clusters/cluster-1/endpoints").mock(
            return_value=httpx.Response(
                200,
                json={
                    "api": "https://cluster-1.api.example.com",
                    "dashboard": "https://cluster-1.dashboard.example.com",
                },
            )
        )

        auth = APIKeyAuth(api_key="test-key")
        http = HttpClient(base_url="https://api.example.com", auth=auth)
        clusters = Clusters(http)

        result = clusters.get_endpoints("cluster-1")

        assert result["api"] == "https://cluster-1.api.example.com"
        assert result["dashboard"] == "https://cluster-1.dashboard.example.com"

    @respx.mock
    def test_clusters_get_metrics(self) -> None:
        """Clusters should get cluster metrics."""
        respx.get("https://api.example.com/clusters/cluster-1/metrics").mock(
            return_value=httpx.Response(
                200,
                json={
                    "cpu_usage": 45.5,
                    "memory_usage": 62.3,
                    "disk_usage": 30.1,
                },
            )
        )

        auth = APIKeyAuth(api_key="test-key")
        http = HttpClient(base_url="https://api.example.com", auth=auth)
        clusters = Clusters(http)

        result = clusters.get_metrics("cluster-1")

        assert result["cpu_usage"] == 45.5
        assert result["memory_usage"] == 62.3
