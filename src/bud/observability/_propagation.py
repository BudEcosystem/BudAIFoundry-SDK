"""W3C propagator setup and context extract/inject helpers.

Sets up CompositePropagator with TraceContext + Baggage for W3C-compliant
distributed trace propagation.
"""

from __future__ import annotations

from typing import Any

from opentelemetry import context, propagate
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.context import Context
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator


def setup_propagator() -> None:
    """Set global propagator to W3C TraceContext + Baggage."""
    propagate.set_global_textmap(
        CompositePropagator(
            [
                TraceContextTextMapPropagator(),
                W3CBaggagePropagator(),
            ]
        )
    )


def extract_context(carrier: dict[str, str]) -> Context:
    """Extract W3C trace context from a dict of HTTP headers."""
    return propagate.extract(carrier=carrier)


def inject_into_headers(headers: dict[str, str] | None = None) -> dict[str, str]:
    """Inject current trace context into outgoing HTTP headers."""
    if headers is None:
        headers = {}
    propagate.inject(carrier=headers)
    return headers


def extract_from_request(request: Any) -> Context:
    """Extract trace context from FastAPI Request, dict carrier, or httpx.Request.

    Handles multiple request types:
    - dict: used directly as carrier
    - FastAPI Request: extracts headers as dict
    - httpx.Request: extracts headers as dict
    - Other: returns current context
    """
    if isinstance(request, dict):
        return extract_context(request)

    # FastAPI Request
    try:
        from starlette.requests import Request as StarletteRequest

        if isinstance(request, StarletteRequest):
            carrier = dict(request.headers)
            return extract_context(carrier)
    except ImportError:
        pass

    # httpx.Request
    try:
        import httpx

        if isinstance(request, httpx.Request):
            carrier = dict(request.headers)
            return extract_context(carrier)
    except ImportError:
        pass

    # Fallback: return current context
    return context.get_current()
