"""Tests for Benchmarks resource."""

from __future__ import annotations

import httpx
import respx

from bud._http import HttpClient
from bud.auth import APIKeyAuth
from bud.resources.benchmarks import Benchmarks


class TestBenchmarksResource:
    """Test Benchmarks resource methods."""

    @respx.mock
    def test_benchmarks_list(self) -> None:
        """Benchmarks should list benchmark results."""
        respx.get("https://api.example.com/benchmark").mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "bench-1",
                            "name": "Performance Test",
                            "status": "completed",
                            "created_at": "2024-01-01T00:00:00Z",
                        },
                        {
                            "id": "bench-2",
                            "name": "Load Test",
                            "status": "running",
                            "created_at": "2024-01-02T00:00:00Z",
                        },
                    ],
                    "total": 2,
                },
            )
        )

        auth = APIKeyAuth(api_key="test-key")
        http = HttpClient(base_url="https://api.example.com", auth=auth)
        benchmarks = Benchmarks(http)

        result = benchmarks.list()

        assert len(result.items) == 2
        assert result.items[0].id == "bench-1"
        assert result.items[0].name == "Performance Test"
        assert result.total == 2

    @respx.mock
    def test_benchmarks_list_with_filters(self) -> None:
        """Benchmarks should list with filters."""
        route = respx.get("https://api.example.com/benchmark").mock(
            return_value=httpx.Response(
                200,
                json={"items": [], "total": 0},
            )
        )

        auth = APIKeyAuth(api_key="test-key")
        http = HttpClient(base_url="https://api.example.com", auth=auth)
        benchmarks = Benchmarks(http)

        benchmarks.list(status="completed", limit=10, offset=0)

        request = route.calls.last.request
        assert "status=completed" in str(request.url)
        assert "limit=10" in str(request.url)

    @respx.mock
    def test_benchmarks_get(self) -> None:
        """Benchmarks should get a single result."""
        respx.get("https://api.example.com/benchmark/result").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "bench-1",
                    "name": "Performance Test",
                    "status": "completed",
                    "created_at": "2024-01-01T00:00:00Z",
                    "results": {"latency_p99": 100, "throughput": 1000},
                },
            )
        )

        auth = APIKeyAuth(api_key="test-key")
        http = HttpClient(base_url="https://api.example.com", auth=auth)
        benchmarks = Benchmarks(http)

        result = benchmarks.get("bench-1")

        assert result.id == "bench-1"
        assert result.status == "completed"

    @respx.mock
    def test_benchmarks_run(self) -> None:
        """Benchmarks should run a benchmark workflow."""
        respx.post("https://api.example.com/benchmark/run-workflow").mock(
            return_value=httpx.Response(
                202,
                json={
                    "id": "bench-new",
                    "name": "New Benchmark",
                    "status": "pending",
                    "created_at": "2024-01-03T00:00:00Z",
                },
            )
        )

        auth = APIKeyAuth(api_key="test-key")
        http = HttpClient(base_url="https://api.example.com", auth=auth)
        benchmarks = Benchmarks(http)

        result = benchmarks.run(
            name="New Benchmark",
            config={"type": "latency", "duration": 60},
        )

        assert result.id == "bench-new"
        assert result.status == "pending"

    @respx.mock
    def test_benchmarks_cancel(self) -> None:
        """Benchmarks should cancel a running benchmark."""
        respx.post("https://api.example.com/benchmark/cancel").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "bench-1",
                    "name": "Test Benchmark",
                    "status": "cancelled",
                },
            )
        )

        auth = APIKeyAuth(api_key="test-key")
        http = HttpClient(base_url="https://api.example.com", auth=auth)
        benchmarks = Benchmarks(http)

        result = benchmarks.cancel("bench-1")

        assert result.status == "cancelled"

    @respx.mock
    def test_benchmarks_get_filters(self) -> None:
        """Benchmarks should get available filter options."""
        respx.get("https://api.example.com/benchmark/filters").mock(
            return_value=httpx.Response(
                200,
                json={
                    "statuses": ["pending", "running", "completed", "failed", "cancelled"],
                    "types": ["latency", "throughput", "stress"],
                },
            )
        )

        auth = APIKeyAuth(api_key="test-key")
        http = HttpClient(base_url="https://api.example.com", auth=auth)
        benchmarks = Benchmarks(http)

        result = benchmarks.get_filters()

        assert "completed" in result.statuses
        assert "latency" in result.types

    @respx.mock
    def test_benchmarks_analyze(self) -> None:
        """Benchmarks should analyze benchmark data."""
        respx.post("https://api.example.com/benchmark/analysis/compare").mock(
            return_value=httpx.Response(
                200,
                json={
                    "comparison": {
                        "baseline_id": "bench-1",
                        "target_id": "bench-2",
                        "improvement_pct": 15.5,
                    },
                },
            )
        )

        auth = APIKeyAuth(api_key="test-key")
        http = HttpClient(base_url="https://api.example.com", auth=auth)
        benchmarks = Benchmarks(http)

        result = benchmarks.analyze(
            analysis_type="compare",
            benchmark_ids=["bench-1", "bench-2"],
        )

        assert "comparison" in result
        assert result["comparison"]["improvement_pct"] == 15.5
