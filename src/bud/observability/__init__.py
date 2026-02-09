"""bud.observability — Unified OTel-native observability for the BudAIFoundry SDK.

Public API:
    configure()          — Main entry point (3-5 lines to set up)
    shutdown()           — Flush and release resources
    is_configured()      — Check if observability is active
    get_tracer()         — Get OTel Tracer (or no-op)
    get_meter()          — Get OTel Meter (or no-op)
    extract_context()    — Extract W3C trace context from headers
    inject_context()     — Inject trace context into headers
    extract_from_request() — Extract context from Request objects
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from bud.observability._config import ObservabilityConfig, ObservabilityMode
from bud.observability._noop import _check_otel_available, _NoOpMeter, _NoOpTracer

logger = logging.getLogger("bud.observability")

if TYPE_CHECKING:
    from bud.observability._baggage import BaggageSpanProcessor  # noqa: F401


def configure(
    api_key: str | None = None,
    *,
    config: ObservabilityConfig | None = None,
    mode: ObservabilityMode | None = None,
    service_name: str | None = None,
    collector_endpoint: str | None = None,
    tracer_provider: Any = None,
    meter_provider: Any = None,
    logger_provider: Any = None,
    instrumentors: list[str] | None = None,
    enabled: bool = True,
) -> None:
    """Configure bud observability. Safe to call even if OTel deps are missing.

    Example:
        from bud.observability import configure
        configure(api_key="bud_client_xxxx")
    """
    try:
        if not _check_otel_available():
            logger.warning(
                "OpenTelemetry SDK not installed. Install with: pip install bud-sdk[observability]"
            )
            return

        if config is None:
            config = ObservabilityConfig._resolve_from_env()

        # Override with explicit arguments
        if api_key is not None:
            config.api_key = api_key
        if mode is not None:
            config.mode = mode
        if service_name is not None:
            config.service_name = service_name
        if collector_endpoint is not None:
            config.collector_endpoint = collector_endpoint
        if tracer_provider is not None:
            config.tracer_provider = tracer_provider
        if meter_provider is not None:
            config.meter_provider = meter_provider
        if logger_provider is not None:
            config.logger_provider = logger_provider
        if instrumentors is not None:
            config.instrumentors = instrumentors
        config.enabled = enabled

        from bud.observability._state import _state

        _state.configure(config)
    except Exception:
        logger.warning("Observability configuration failed", exc_info=True)


def shutdown() -> None:
    """Flush pending telemetry and release resources."""
    try:
        from bud.observability._state import _state

        _state.shutdown()
    except Exception:
        logger.debug("Observability shutdown error", exc_info=True)


def is_configured() -> bool:
    """Check whether observability has been configured."""
    try:
        from bud.observability._state import _state

        return _state.is_configured
    except Exception:
        return False


def get_tracer(name: str = "bud") -> Any:
    """Return an OTel Tracer for manual span creation. Returns no-op if not configured."""
    try:
        from bud.observability._state import _state

        return _state.get_tracer(name)
    except Exception:
        return _NoOpTracer()


def get_meter(name: str = "bud") -> Any:
    """Return an OTel Meter for custom metrics. Returns no-op if not configured."""
    try:
        from bud.observability._state import _state

        return _state.get_meter(name)
    except Exception:
        return _NoOpMeter()


def extract_context(carrier: dict[str, str]) -> Any:
    """Extract W3C trace context from a dict of HTTP headers."""
    try:
        from bud.observability._propagation import extract_context as _extract

        return _extract(carrier)
    except Exception:
        return None


def inject_context(carrier: dict[str, str]) -> dict[str, str]:
    """Inject current trace context into outgoing HTTP headers."""
    try:
        from bud.observability._propagation import inject_into_headers

        return inject_into_headers(carrier)
    except Exception:
        return carrier


def extract_from_request(request: Any) -> Any:
    """Extract trace context from FastAPI Request, dict, or httpx.Request."""
    try:
        from bud.observability._propagation import extract_from_request as _extract

        return _extract(request)
    except Exception:
        return None


def create_traced_span(
    name: str, tracer: Any = None, attributes: dict[str, Any] | None = None
) -> tuple[Any, Any]:
    """Create a span and attach it to the current context.

    Returns (span, context_token) for use with TracedStream or manual lifecycle.
    """
    from opentelemetry import context as _ctx, trace as _trace

    if tracer is None:
        tracer = get_tracer()
    span = tracer.start_span(name)
    if attributes:
        for k, v in attributes.items():
            span.set_attribute(k, v)
    ctx = _trace.set_span_in_context(span)
    token = _ctx.attach(ctx)
    return span, token


def get_current_span(ctx: Any = None) -> Any:
    """Return the current span, optionally from a specific context."""
    from opentelemetry import trace as _trace

    if ctx is not None:
        return _trace.get_current_span(ctx)
    return _trace.get_current_span()


def _lazy_traced_stream() -> type:
    from bud.observability._stream_wrapper import TracedStream

    return TracedStream


def __getattr__(name: str) -> Any:
    if name == "TracedStream":
        return _lazy_traced_stream()
    if name == "track":
        from bud.observability._track import track

        return track
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "configure",
    "shutdown",
    "is_configured",
    "get_tracer",
    "get_meter",
    "extract_context",
    "inject_context",
    "extract_from_request",
    "create_traced_span",
    "get_current_span",
    "ObservabilityConfig",
    "ObservabilityMode",
    "BaggageSpanProcessor",
    "TracedStream",
    "track",
]
