"""Authenticated OTLP HTTP exporters for traces, metrics, and logs.

Wraps standard OTLP HTTP exporters, injecting Authorization: Bearer <api_key>
and X-Bud-SDK-Version headers on every export request.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

if TYPE_CHECKING:
    from opentelemetry.sdk.metrics.export import MetricExporter
    from opentelemetry.sdk.trace.export import SpanExporter

    from bud.observability._config import ObservabilityConfig


def _build_headers(config: ObservabilityConfig) -> dict[str, str]:
    """Build auth and SDK version headers for OTLP exporters."""
    from bud._version import __version__

    headers: dict[str, str] = {}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    headers["X-Bud-SDK-Version"] = __version__
    return headers


def create_trace_exporter(config: ObservabilityConfig) -> SpanExporter:
    """Create an OTLP HTTP span exporter with auth headers."""
    from opentelemetry.exporter.otlp.proto.http import Compression

    headers = _build_headers(config)
    compression = Compression.Gzip if config.compression == "gzip" else Compression.NoCompression
    return OTLPSpanExporter(
        endpoint=f"{config.collector_endpoint}/v1/traces",
        headers=headers,
        timeout=config.export_timeout_ms // 1000,
        compression=compression,
    )


def create_metric_exporter(config: ObservabilityConfig) -> MetricExporter:
    """Create an OTLP HTTP metric exporter with auth headers."""
    from opentelemetry.exporter.otlp.proto.http import Compression

    headers = _build_headers(config)
    compression = Compression.Gzip if config.compression == "gzip" else Compression.NoCompression
    return OTLPMetricExporter(
        endpoint=f"{config.collector_endpoint}/v1/metrics",
        headers=headers,
        timeout=config.export_timeout_ms // 1000,
        compression=compression,
    )


def create_log_exporter(config: ObservabilityConfig) -> object:
    """Create an OTLP HTTP log exporter with auth headers.

    Returns object type since opentelemetry-exporter-otlp-proto-http log exporter
    may not be available in all versions.
    """
    from opentelemetry.exporter.otlp.proto.http import Compression
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter

    headers = _build_headers(config)
    compression = Compression.Gzip if config.compression == "gzip" else Compression.NoCompression
    return OTLPLogExporter(
        endpoint=f"{config.collector_endpoint}/v1/logs",
        headers=headers,
        timeout=config.export_timeout_ms // 1000,
        compression=compression,
    )
