"""Benchmarks resource for BudAI SDK."""

from __future__ import annotations

import builtins
from typing import TYPE_CHECKING, Any

from bud.models.benchmark import Benchmark, BenchmarkFilters, BenchmarkList
from bud.resources._base import SyncResource

if TYPE_CHECKING:
    from bud._http import HttpClient


class Benchmarks(SyncResource):
    """Benchmarks resource for performance testing.

    Example:
        ```python
        from bud import BudClient

        client = BudClient(api_key="your-key")

        # Run a benchmark
        benchmark = client.benchmarks.run(
            name="Latency Test",
            config={"type": "latency", "duration": 60},
        )

        # List benchmarks
        results = client.benchmarks.list(status="completed")
        for bench in results.items:
            print(f"{bench.name}: {bench.status}")

        # Get a specific result
        result = client.benchmarks.get("benchmark-id")
        print(result.results)
        ```
    """

    def __init__(self, http: HttpClient) -> None:
        """Initialize benchmarks resource.

        Args:
            http: HTTP client instance.
        """
        super().__init__(http)

    def list(
        self,
        *,
        status: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> BenchmarkList:
        """List benchmark results.

        Args:
            status: Filter by status (pending, running, completed, failed, cancelled).
            limit: Maximum number of results to return.
            offset: Number of results to skip.

        Returns:
            BenchmarkList with items and pagination info.
        """
        params: dict[str, Any] = {}
        if status:
            params["status"] = status
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset

        data = self._http.get("/benchmark", params=params)
        return BenchmarkList.model_validate(data)

    def get(self, benchmark_id: str) -> Benchmark:
        """Get a specific benchmark result.

        Args:
            benchmark_id: The benchmark ID.

        Returns:
            Benchmark result.
        """
        data = self._http.get("/benchmark/result", params={"id": benchmark_id})
        return Benchmark.model_validate(data)

    def run(
        self,
        name: str,
        config: dict[str, Any],
    ) -> Benchmark:
        """Run a new benchmark.

        Args:
            name: Benchmark name.
            config: Benchmark configuration.

        Returns:
            Created benchmark (status will be pending/running).
        """
        data = self._http.post(
            "/benchmark/run-workflow",
            json={"name": name, "config": config},
        )
        return Benchmark.model_validate(data)

    def cancel(self, benchmark_id: str) -> Benchmark:
        """Cancel a running benchmark.

        Args:
            benchmark_id: The benchmark ID to cancel.

        Returns:
            Cancelled benchmark.
        """
        data = self._http.post(
            "/benchmark/cancel",
            json={"id": benchmark_id},
        )
        return Benchmark.model_validate(data)

    def get_filters(self) -> BenchmarkFilters:
        """Get available filter options.

        Returns:
            BenchmarkFilters with available status and type values.
        """
        data = self._http.get("/benchmark/filters")
        return BenchmarkFilters.model_validate(data)

    def analyze(
        self,
        analysis_type: str,
        benchmark_ids: builtins.list[str],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Analyze benchmark data.

        Args:
            analysis_type: Type of analysis (e.g., "compare", "trend").
            benchmark_ids: List of benchmark IDs to analyze.
            **kwargs: Additional analysis parameters.

        Returns:
            Analysis results as dictionary.
        """
        payload = {
            "benchmark_ids": benchmark_ids,
            **kwargs,
        }
        data = self._http.post(f"/benchmark/analysis/{analysis_type}", json=payload)
        return data


class AsyncBenchmarks:
    """Async benchmarks resource for performance testing."""

    def __init__(self, http) -> None:
        """Initialize async benchmarks resource.

        Args:
            http: Async HTTP client instance.
        """
        self._http = http

    async def list(
        self,
        *,
        status: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> BenchmarkList:
        """List benchmark results."""
        params: dict[str, Any] = {}
        if status:
            params["status"] = status
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset

        data = await self._http.get("/benchmark", params=params)
        return BenchmarkList.model_validate(data)

    async def get(self, benchmark_id: str) -> Benchmark:
        """Get a specific benchmark result."""
        data = await self._http.get("/benchmark/result", params={"id": benchmark_id})
        return Benchmark.model_validate(data)

    async def run(
        self,
        name: str,
        config: dict[str, Any],
    ) -> Benchmark:
        """Run a new benchmark."""
        data = await self._http.post(
            "/benchmark/run-workflow",
            json={"name": name, "config": config},
        )
        return Benchmark.model_validate(data)

    async def cancel(self, benchmark_id: str) -> Benchmark:
        """Cancel a running benchmark."""
        data = await self._http.post(
            "/benchmark/cancel",
            json={"id": benchmark_id},
        )
        return Benchmark.model_validate(data)

    async def get_filters(self) -> BenchmarkFilters:
        """Get available filter options."""
        data = await self._http.get("/benchmark/filters")
        return BenchmarkFilters.model_validate(data)

    async def analyze(
        self,
        analysis_type: str,
        benchmark_ids: builtins.list[str],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Analyze benchmark data."""
        payload = {
            "benchmark_ids": benchmark_ids,
            **kwargs,
        }
        data = await self._http.post(f"/benchmark/analysis/{analysis_type}", json=payload)
        return data
