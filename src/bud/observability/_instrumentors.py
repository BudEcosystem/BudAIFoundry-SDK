"""Explicit instrumentation helpers for FastAPI, HTTPX, etc.

Usage:
    from bud.observability import instrument_fastapi, instrument_httpx

    configure(client=client)
    app = FastAPI()
    instrument_fastapi(app)
    instrument_httpx()
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("bud.observability")


def instrument_fastapi(app: Any, **kwargs: Any) -> None:
    """Instrument a FastAPI app for distributed tracing.

    Call after configure() and after creating the app.
    Requires: pip install bud-sdk[observability-fastapi]

    Args:
        app: The FastAPI application instance.
        **kwargs: Additional kwargs forwarded to
            FastAPIInstrumentor.instrument_app().
    """
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        from bud.observability._state import _state

        FastAPIInstrumentor.instrument_app(
            app,
            tracer_provider=_state._tracer_provider,
            **kwargs,
        )
    except ImportError:
        logger.warning(
            "FastAPI instrumentation not installed. "
            "Install with: pip install bud-sdk[observability-fastapi]"
        )
    except Exception:
        logger.warning("Failed to instrument FastAPI app", exc_info=True)


def instrument_httpx(client: Any = None, **kwargs: Any) -> None:
    """Instrument httpx for distributed tracing.

    Call after configure().
    Requires: pip install bud-sdk[observability-httpx]

    Args:
        client: Optional httpx.Client or httpx.AsyncClient.
            When None, instruments all httpx clients globally.
            When provided, instruments only the given client.
        **kwargs: Additional kwargs forwarded to the instrumentor.
    """
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        from bud.observability._state import _state

        instrumentor = HTTPXClientInstrumentor()
        if client is None:
            instrumentor.instrument(
                tracer_provider=_state._tracer_provider, **kwargs
            )
        else:
            instrumentor.instrument_client(
                client, tracer_provider=_state._tracer_provider, **kwargs
            )
    except ImportError:
        logger.warning(
            "HTTPX instrumentation not installed. "
            "Install with: pip install bud-sdk[observability-httpx]"
        )
    except Exception:
        logger.warning("Failed to instrument httpx", exc_info=True)
