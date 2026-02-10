#!/usr/bin/env python3
"""FastAPI auto-instrumentation with Bud SDK observability.

Demonstrates how ``configure(instrumentors=["fastapi", "httpx"])`` enables
automatic distributed tracing for a FastAPI service — no ``@track`` or manual
spans required for basic coverage.  The example also shows how ``@track`` and
manual spans nest cleanly under the auto-created route spans.

Trace tree produced (for ``POST /chat``)::

    POST /chat                    (auto — FastAPI instrumentor)
      ├── validate-request        (@track decorator, type="tool")
      ├── HTTP POST …/completions (auto — httpx instrumentor)
      └── format-response         (manual span via get_tracer)

When the caller sends a ``traceparent`` header, all spans join the caller's
trace — enabling end-to-end distributed tracing across services.

Gateway-side spans (if BudGateway has observability enabled)::

    POST /chat                    (FastAPI auto)
      ├── validate-request        (@track)
      ├── HTTP POST …/completions (httpx auto)
      │     └── POST /v1/chat/completions  (budgateway)
      │           └── function_inference   (budgateway)
      │                 └── ...            (budgateway chain)
      └── format-response         (manual)

Prerequisites::

    pip install bud-sdk[observability-fastapi,observability-httpx] uvicorn

Usage::

    # Terminal 1 — start the server
    BUD_API_KEY=my-test-api-key python examples/observability/fastapi_instrumentation.py

    # Terminal 2 — basic request
    curl -X POST http://localhost:8000/chat \\
      -H "Content-Type: application/json" \\
      -d '{"message": "What is RAG?"}'

    # With distributed tracing (propagate caller's trace)
    curl -X POST http://localhost:8000/chat \\
      -H "Content-Type: application/json" \\
      -H "traceparent: 00-abcdef1234567890abcdef1234567890-1234567890abcdef-01" \\
      -d '{"message": "What is RAG?"}'

    # Health check (also traced automatically)
    curl http://localhost:8000/health
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from pydantic import BaseModel

from bud import BudClient
from bud.observability import configure, extract_from_request, get_tracer, shutdown, track

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_URL = os.environ.get("BUD_BASE_URL", "http://localhost:56054")
API_KEY = os.environ.get("BUD_API_KEY", "my-test-api-key")

# ---------------------------------------------------------------------------
# Observability — call configure() BEFORE importing FastAPI.
# The FastAPI instrumentor monkey-patches ``fastapi.FastAPI``, so we must
# import FastAPI *after* configure() to pick up the patched class.
# ---------------------------------------------------------------------------
client = BudClient(api_key=API_KEY, base_url=BASE_URL)
configure(
    client=client,
    service_name="fastapi-instrumented-example",
    instrumentors=["fastapi", "httpx"],
)

from fastapi import FastAPI, Request  # noqa: E402 — must be after configure()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    client.close()
    shutdown()


# ---------------------------------------------------------------------------
# App and tracer
# ---------------------------------------------------------------------------
app = FastAPI(title="Instrumented Chat Service", lifespan=lifespan)
tracer = get_tracer("chat-service")


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    """Incoming chat request."""

    message: str
    model: str = "gpt"


class ChatResponse(BaseModel):
    """Outgoing chat response."""

    reply: str
    model: str
    trace_id: str | None = None


# ---------------------------------------------------------------------------
# Helper — @track nests under the auto-created route span
# ---------------------------------------------------------------------------
@track(name="validate-request", type="tool")
def validate_request(req: ChatRequest) -> ChatRequest:
    """Validate and normalise the incoming request.

    This span appears as a child of the auto-created ``POST /chat`` route span
    produced by the FastAPI instrumentor.
    """
    req.message = req.message.strip()
    if not req.message:
        raise ValueError("message must not be empty")
    return req


# ---------------------------------------------------------------------------
# POST /chat — the main endpoint
# ---------------------------------------------------------------------------
@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest, request: Request) -> ChatResponse:
    """Handle a chat request.

    What happens automatically (no code needed):
    - FastAPI instrumentor creates a span for ``POST /chat``
    - httpx instrumentor creates a child span for the outgoing
      ``client.chat.completions.create()`` call

    What this handler adds on top:
    - ``extract_from_request(request)`` for manual W3C context access
    - ``@track`` on ``validate_request()`` creates a child span
    - ``tracer.start_as_current_span("format-response")`` creates a manual child span
    """
    # Show manual context extraction (useful for custom propagation logic).
    # When the caller sends a traceparent header, this context links all spans
    # to the caller's trace.  The FastAPI instrumentor already handles this
    # automatically, so this call is purely illustrative.
    ctx = extract_from_request(request)
    _ = ctx  # available for custom use if needed

    # @track child span: validate-request
    validated = validate_request(req)

    # httpx auto-span: the outgoing HTTP call is traced automatically
    response = client.chat.completions.create(
        model=validated.model,
        messages=[{"role": "user", "content": validated.message}],
    )

    reply = response.choices[0].message.content or ""

    # Manual child span: format-response
    with tracer.start_as_current_span("format-response") as span:
        span.set_attribute("response.length", len(reply))
        result = ChatResponse(
            reply=reply,
            model=validated.model,
        )

    return result


# ---------------------------------------------------------------------------
# GET /health — minimal endpoint, still auto-instrumented
# ---------------------------------------------------------------------------
@app.get("/health")
async def health() -> dict[str, str]:
    """Health check.

    Even this minimal endpoint gets an automatic span from the FastAPI
    instrumentor — no decorators or manual code required.
    """
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Run with uvicorn
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
