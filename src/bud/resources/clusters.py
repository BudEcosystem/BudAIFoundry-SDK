"""Clusters resource for BudAI SDK."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from bud.models.cluster import Cluster, ClusterList
from bud.resources._base import SyncResource

if TYPE_CHECKING:
    from bud._http import HttpClient


class Clusters(SyncResource):
    """Clusters resource for managing compute clusters.

    Example:
        ```python
        from bud import BudClient

        client = BudClient(api_key="your-key")

        # List clusters
        clusters = client.clusters.list()
        for cluster in clusters.items:
            print(f"{cluster.name}: {cluster.status}")

        # Create a cluster
        cluster = client.clusters.create(
            name="My Cluster",
            node_count=3,
            config={"region": "us-east-1"},
        )

        # Get cluster metrics
        metrics = client.clusters.get_metrics(cluster.id)
        print(f"CPU: {metrics['cpu_usage']}%")
        ```
    """

    def __init__(self, http: HttpClient) -> None:
        """Initialize clusters resource.

        Args:
            http: HTTP client instance.
        """
        super().__init__(http)

    def list(self) -> ClusterList:
        """List all clusters.

        Returns:
            ClusterList with items.
        """
        data = self._http.get("/clusters/clusters")
        return ClusterList.model_validate(data)

    def get(self, cluster_id: str) -> Cluster:
        """Get a specific cluster.

        Args:
            cluster_id: The cluster ID.

        Returns:
            Cluster details.
        """
        data = self._http.get(f"/clusters/{cluster_id}")
        return Cluster.model_validate(data)

    def create(
        self,
        name: str,
        node_count: int,
        config: dict[str, Any] | None = None,
    ) -> Cluster:
        """Create a new cluster.

        Args:
            name: Cluster name.
            node_count: Number of nodes.
            config: Optional cluster configuration.

        Returns:
            Created cluster.
        """
        payload = {
            "name": name,
            "node_count": node_count,
        }
        if config:
            payload["config"] = config

        data = self._http.post("/clusters/clusters", json=payload)
        return Cluster.model_validate(data)

    def update(
        self,
        cluster_id: str,
        *,
        name: str | None = None,
        node_count: int | None = None,
        config: dict[str, Any] | None = None,
    ) -> Cluster:
        """Update a cluster.

        Args:
            cluster_id: The cluster ID.
            name: New cluster name.
            node_count: New node count.
            config: New configuration.

        Returns:
            Updated cluster.
        """
        payload = {}
        if name is not None:
            payload["name"] = name
        if node_count is not None:
            payload["node_count"] = node_count
        if config is not None:
            payload["config"] = config

        data = self._http.patch(f"/clusters/{cluster_id}", json=payload)
        return Cluster.model_validate(data)

    def delete(self, cluster_id: str) -> None:
        """Delete a cluster.

        Args:
            cluster_id: The cluster ID to delete.
        """
        self._http.post(f"/clusters/{cluster_id}/delete-workflow")

    def get_endpoints(self, cluster_id: str) -> dict[str, str]:
        """Get cluster endpoints.

        Args:
            cluster_id: The cluster ID.

        Returns:
            Dictionary of endpoint names to URLs.
        """
        return self._http.get(f"/clusters/{cluster_id}/endpoints")

    def get_metrics(self, cluster_id: str) -> dict[str, Any]:
        """Get cluster metrics.

        Args:
            cluster_id: The cluster ID.

        Returns:
            Dictionary of metric names to values.
        """
        return self._http.get(f"/clusters/{cluster_id}/metrics")


class AsyncClusters:
    """Async clusters resource for managing compute clusters."""

    def __init__(self, http) -> None:
        """Initialize async clusters resource.

        Args:
            http: Async HTTP client instance.
        """
        self._http = http

    async def list(self) -> ClusterList:
        """List all clusters."""
        data = await self._http.get("/clusters/clusters")
        return ClusterList.model_validate(data)

    async def get(self, cluster_id: str) -> Cluster:
        """Get a specific cluster."""
        data = await self._http.get(f"/clusters/{cluster_id}")
        return Cluster.model_validate(data)

    async def create(
        self,
        name: str,
        node_count: int,
        config: dict[str, Any] | None = None,
    ) -> Cluster:
        """Create a new cluster."""
        payload = {
            "name": name,
            "node_count": node_count,
        }
        if config:
            payload["config"] = config

        data = await self._http.post("/clusters/clusters", json=payload)
        return Cluster.model_validate(data)

    async def update(
        self,
        cluster_id: str,
        *,
        name: str | None = None,
        node_count: int | None = None,
        config: dict[str, Any] | None = None,
    ) -> Cluster:
        """Update a cluster."""
        payload = {}
        if name is not None:
            payload["name"] = name
        if node_count is not None:
            payload["node_count"] = node_count
        if config is not None:
            payload["config"] = config

        data = await self._http.patch(f"/clusters/{cluster_id}", json=payload)
        return Cluster.model_validate(data)

    async def delete(self, cluster_id: str) -> None:
        """Delete a cluster."""
        await self._http.post(f"/clusters/{cluster_id}/delete-workflow")

    async def get_endpoints(self, cluster_id: str) -> dict[str, str]:
        """Get cluster endpoints."""
        return await self._http.get(f"/clusters/{cluster_id}/endpoints")

    async def get_metrics(self, cluster_id: str) -> dict[str, Any]:
        """Get cluster metrics."""
        return await self._http.get(f"/clusters/{cluster_id}/metrics")
