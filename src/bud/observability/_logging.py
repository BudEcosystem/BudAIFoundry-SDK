"""Python logging to OTel LoggerProvider bridge.

Bridges Python's standard logging module to OTel's LoggerProvider so that
log records become OTel log records exported to the collector with trace correlation.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from bud.observability._config import ObservabilityConfig


def setup_log_provider(config: ObservabilityConfig, resource: Any = None) -> Any:
    """Create a LoggerProvider with BatchLogRecordProcessor and OTLP exporter.

    Args:
        config: ObservabilityConfig with collector endpoint and auth settings.
        resource: Optional OTel Resource to attach to all log records.

    Returns:
        LoggerProvider instance.
    """
    from opentelemetry.sdk._logs import LoggerProvider
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

    from bud.observability._exporter import create_log_exporter

    log_exporter = create_log_exporter(config)
    logger_provider = LoggerProvider(resource=resource) if resource else LoggerProvider()
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))  # type: ignore[arg-type]
    return logger_provider


def setup_log_bridge(logger_provider: Any, min_level: str = "WARNING") -> None:
    """Attach OTel LoggingHandler to Python root logger.

    Args:
        logger_provider: An OTel LoggerProvider instance.
        min_level: Minimum log level to export (default: WARNING).
    """
    from opentelemetry.sdk._logs import LoggingHandler

    level = getattr(logging, min_level.upper(), logging.WARNING)
    handler = LoggingHandler(
        level=level,
        logger_provider=logger_provider,
    )
    root = logging.getLogger()
    root.addHandler(handler)
    # Ensure the root logger passes records at the requested level to handlers.
    # Without this, the root logger's default WARNING gate drops lower-level records
    # before they ever reach the OTel handler.
    if root.level > level:
        root.setLevel(level)
