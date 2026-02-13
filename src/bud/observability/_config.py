"""ObservabilityConfig dataclass and ObservabilityMode enum.

Configuration precedence:
1. Explicit constructor arguments (highest)
2. Values from ``client`` parameter
3. BUD_API_KEY / BUD_BASE_URL environment variables
4. Defaults (lowest)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ObservabilityMode(str, Enum):
    """Provider strategy for observability setup."""

    AUTO = "auto"
    CREATE = "create"
    ATTACH = "attach"
    INTERNAL = "internal"
    DISABLED = "disabled"


def _env(bud_key: str, otel_key: str | None = None, default: str | None = None) -> str | None:
    """Resolve an env var with BUD_OTEL_ prefix first, then OTEL_ fallback."""
    value = os.environ.get(bud_key)
    if value is not None:
        return value
    if otel_key:
        value = os.environ.get(otel_key)
        if value is not None:
            return value
    return default


@dataclass
class ObservabilityConfig:
    """Full configuration for the observability module."""

    # Core
    mode: ObservabilityMode = ObservabilityMode.AUTO
    api_key: str | None = None
    collector_endpoint: str | None = None
    service_name: str = "bud-sdk-client"
    enabled: bool = True

    # Resource attributes
    service_version: str | None = None
    deployment_environment: str | None = None
    resource_attributes: dict[str, str] = field(default_factory=dict)

    # Traces — BatchSpanProcessor tuning
    traces_enabled: bool = True
    batch_max_queue_size: int = 2048
    batch_max_export_size: int = 512
    batch_schedule_delay_ms: int = 1000
    export_timeout_ms: int = 5000

    # Metrics — PeriodicExportingMetricReader tuning
    metrics_enabled: bool = True
    metrics_export_interval_ms: int = 60000

    # Logs
    logs_enabled: bool = True
    log_level: str = "WARNING"

    # Network
    compression: str = "gzip"
    tls_insecure: bool = False

    # External providers (for ATTACH mode)
    tracer_provider: Any = None
    meter_provider: Any = None
    logger_provider: Any = None

    @classmethod
    def _resolve_from_env(cls) -> ObservabilityConfig:
        """Create a config resolved from environment variables."""
        mode_str = _env("BUD_OTEL_MODE", default="auto")
        try:
            mode = ObservabilityMode(mode_str.lower()) if mode_str else ObservabilityMode.AUTO
        except ValueError:
            mode = ObservabilityMode.AUTO

        enabled_str = _env("BUD_OTEL_ENABLED", default="true")
        enabled = enabled_str.lower() not in ("false", "0", "no") if enabled_str else True

        return cls(
            mode=mode,
            api_key=os.environ.get("BUD_API_KEY"),
            collector_endpoint=os.environ.get("BUD_BASE_URL"),
            service_name=_env("BUD_OTEL_SERVICE_NAME", "OTEL_SERVICE_NAME", "bud-sdk-client")
            or "bud-sdk-client",
            enabled=enabled,
        )

    def _apply_internal_defaults(self) -> None:
        """Apply aggressive defaults for INTERNAL mode."""
        if self.mode == ObservabilityMode.INTERNAL:
            self.batch_max_queue_size = 4096
            self.batch_max_export_size = 1024
            self.batch_schedule_delay_ms = 2000
            self.metrics_export_interval_ms = 30000
            self.compression = "none"
