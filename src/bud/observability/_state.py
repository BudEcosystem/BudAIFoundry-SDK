"""Thread-safe singleton managing all provider lifecycle.

Provides idempotent configure(), shutdown(), and accessor methods.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from bud.observability._config import ObservabilityConfig, ObservabilityMode
from bud.observability._noop import _NoOpMeter, _NoOpTracer

logger = logging.getLogger("bud.observability")


class _ObservabilityState:
    """Thread-safe singleton for observability provider lifecycle."""

    def __init__(self) -> None:
        self._config: ObservabilityConfig | None = None
        self._tracer_provider: Any = None
        self._meter_provider: Any = None
        self._logger_provider: Any = None
        self._owned_providers: bool = False
        self._is_configured: bool = False
        self._lock = threading.Lock()

    @property
    def is_configured(self) -> bool:
        return self._is_configured

    def configure(self, config: ObservabilityConfig) -> None:
        """Configure observability. Idempotent: second call warns and no-ops."""
        with self._lock:
            if self._is_configured:
                logger.warning("Observability already configured, skipping reconfiguration")
                return

            if not config.enabled or config.mode == ObservabilityMode.DISABLED:
                logger.info("Observability disabled")
                self._is_configured = True
                self._config = config
                return

            from bud.observability._provider import (
                ProviderBundle,
                attach_to_providers,
                create_providers,
                detect_mode,
            )

            # Apply internal defaults if INTERNAL mode
            config._apply_internal_defaults()

            resolved_mode = detect_mode(config)
            logger.info("Observability mode: %s", resolved_mode.value)

            bundle: ProviderBundle
            if resolved_mode == ObservabilityMode.ATTACH:
                bundle = attach_to_providers(config)
            else:
                bundle = create_providers(config)

            self._tracer_provider = bundle.tracer_provider
            self._meter_provider = bundle.meter_provider
            self._logger_provider = bundle.logger_provider
            self._owned_providers = bundle.owned
            self._config = config

            self._is_configured = True
            logger.info("Observability configured successfully")

    def shutdown(self) -> None:
        """Flush and shut down all owned providers."""
        with self._lock:
            if not self._is_configured:
                return

            if self._owned_providers:
                for provider in [
                    self._tracer_provider,
                    self._meter_provider,
                    self._logger_provider,
                ]:
                    if provider is not None and hasattr(provider, "shutdown"):
                        try:
                            provider.shutdown()
                        except Exception:
                            logger.debug("Provider shutdown error", exc_info=True)

            self._tracer_provider = None
            self._meter_provider = None
            self._logger_provider = None
            self._is_configured = False
            self._config = None
            self._owned_providers = False

    def get_tracer(self, name: str = "bud") -> Any:
        """Return a tracer from the provider, or a no-op tracer."""
        if self._tracer_provider is not None:
            return self._tracer_provider.get_tracer(name)
        return _NoOpTracer()

    def get_meter(self, name: str = "bud") -> Any:
        """Return a meter from the provider, or a no-op meter."""
        if self._meter_provider is not None:
            return self._meter_provider.get_meter(name)
        return _NoOpMeter()


# Module-level singleton
_state = _ObservabilityState()
