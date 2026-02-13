"""Authenticated OTLP HTTP exporters for traces, metrics, and logs.

Wraps standard OTLP HTTP exporters, injecting Authorization: Bearer <api_key>
and X-Bud-SDK-Version headers on every export request.

Includes retry logic to handle transient export failures (e.g. gateway proxy
timeouts) that would otherwise cause permanent span loss in the
BatchSpanProcessor.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from typing import TYPE_CHECKING

from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

if TYPE_CHECKING:
    from opentelemetry.sdk.metrics.export import MetricExporter
    from opentelemetry.sdk.trace import ReadableSpan

    from bud.observability._config import ObservabilityConfig

logger = logging.getLogger("bud.observability")


def _build_headers(config: ObservabilityConfig) -> dict[str, str]:
    """Build auth and SDK version headers for OTLP exporters."""
    from bud._version import __version__

    headers: dict[str, str] = {}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    headers["X-Bud-SDK-Version"] = __version__
    return headers


class _RetrySpanExporter(SpanExporter):
    """Wraps a SpanExporter with retry logic for transient failures.

    The standard BatchSpanProcessor drops spans permanently on export failure.
    This wrapper retries the export up to ``max_retries`` times with exponential
    backoff, preventing span loss from transient collector/proxy timeouts.
    """

    def __init__(
        self,
        inner: SpanExporter,
        max_retries: int = 3,
        initial_backoff_s: float = 1.0,
    ) -> None:
        self._inner = inner
        self._max_retries = max_retries
        self._initial_backoff_s = initial_backoff_s

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        last_result = SpanExportResult.FAILURE
        backoff = self._initial_backoff_s
        for attempt in range(1 + self._max_retries):
            try:
                last_result = self._inner.export(spans)
                if last_result == SpanExportResult.SUCCESS:
                    return last_result
            except Exception:
                logger.debug(
                    "Span export attempt %d/%d failed",
                    attempt + 1,
                    1 + self._max_retries,
                    exc_info=True,
                )
            if attempt < self._max_retries:
                logger.debug("Retrying span export in %.1fs", backoff)
                time.sleep(backoff)
                backoff *= 2
        return last_result

    def shutdown(self) -> None:
        try:
            self._inner.shutdown()
        except Exception:
            logger.debug("Inner exporter shutdown failed", exc_info=True)

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        if hasattr(self._inner, "force_flush"):
            try:
                return self._inner.force_flush(timeout_millis)
            except Exception:
                logger.debug("Inner exporter force_flush failed", exc_info=True)
                return False
        return True


def create_trace_exporter(config: ObservabilityConfig) -> SpanExporter:
    """Create an OTLP HTTP span exporter with auth headers and retry logic."""
    from opentelemetry.exporter.otlp.proto.http import Compression

    headers = _build_headers(config)
    compression = Compression.Gzip if config.compression == "gzip" else Compression.NoCompression
    inner = OTLPSpanExporter(
        endpoint=f"{config.collector_endpoint}/v1/traces",
        headers=headers,
        timeout=config.export_timeout_ms // 1000,
        compression=compression,
    )
    return _RetrySpanExporter(inner, max_retries=3, initial_backoff_s=0.5)


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
