"""Auto-instrumentation registry with double-instrumentation guard.

Supports: httpx, requests, fastapi, pydantic_ai.
Missing dependency → debug log, skip. Failed instrumentation → warning log, continue.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("bud.observability")


def _instrument_httpx(tracer_provider: Any) -> None:
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

    if not HTTPXClientInstrumentor().is_instrumented_by_opentelemetry:
        HTTPXClientInstrumentor().instrument(tracer_provider=tracer_provider)


def _instrument_requests(tracer_provider: Any) -> None:
    from opentelemetry.instrumentation.requests import RequestsInstrumentor

    if not RequestsInstrumentor().is_instrumented_by_opentelemetry:
        RequestsInstrumentor().instrument(tracer_provider=tracer_provider)


def _instrument_fastapi(tracer_provider: Any) -> None:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    if not FastAPIInstrumentor().is_instrumented_by_opentelemetry:
        FastAPIInstrumentor().instrument(tracer_provider=tracer_provider)


def _instrument_pydantic_ai(tracer_provider: Any) -> None:
    from opentelemetry.instrumentation.pydantic_ai import PydanticAIInstrumentor

    if not PydanticAIInstrumentor().is_instrumented_by_opentelemetry:
        PydanticAIInstrumentor().instrument(tracer_provider=tracer_provider)


class InstrumentorRegistry:
    """Registry of auto-instrumentors with double-instrumentation guard."""

    _REGISTRY: dict[str, Any] = {
        "httpx": _instrument_httpx,
        "requests": _instrument_requests,
        "fastapi": _instrument_fastapi,
        "pydantic_ai": _instrument_pydantic_ai,
    }

    @classmethod
    def register_all(cls, names: list[str], tracer_provider: Any) -> list[str]:
        """Enable requested instrumentors, returning list of actually enabled ones."""
        enabled: list[str] = []
        for name in names:
            handler = cls._REGISTRY.get(name)
            if handler is None:
                logger.debug("Instrumentor '%s' not in registry, skipping", name)
                continue
            try:
                handler(tracer_provider)
                enabled.append(name)
            except ImportError:
                logger.debug("Instrumentor '%s' skipped: dependency not installed", name)
            except Exception as exc:
                logger.warning("Instrumentor '%s' failed: %s", name, exc)
        return enabled
