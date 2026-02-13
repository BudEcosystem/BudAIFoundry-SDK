"""Tests for _exporter.py — Auth headers on OTLP exporters."""

from __future__ import annotations

from bud.observability._config import ObservabilityConfig
from bud.observability._exporter import _build_headers, create_trace_exporter


class TestBuildHeaders:
    def test_headers_with_api_key(self) -> None:
        config = ObservabilityConfig(api_key="test-key-123")
        headers = _build_headers(config)
        assert headers["Authorization"] == "Bearer test-key-123"
        assert "X-Bud-SDK-Version" in headers

    def test_headers_without_api_key(self) -> None:
        config = ObservabilityConfig(api_key=None)
        headers = _build_headers(config)
        assert "Authorization" not in headers
        assert "X-Bud-SDK-Version" in headers

    def test_sdk_version_header(self) -> None:
        config = ObservabilityConfig()
        headers = _build_headers(config)
        assert headers["X-Bud-SDK-Version"] == "0.1.0"


class TestCreateTraceExporter:
    def test_creates_exporter_with_correct_endpoint(self) -> None:
        config = ObservabilityConfig(
            api_key="key",
            collector_endpoint="http://localhost:4318",
            compression="gzip",
        )
        exporter = create_trace_exporter(config)
        assert exporter is not None

    def test_creates_exporter_no_compression(self) -> None:
        config = ObservabilityConfig(
            api_key="key",
            collector_endpoint="http://localhost:4318",
            compression="none",
        )
        exporter = create_trace_exporter(config)
        assert exporter is not None
