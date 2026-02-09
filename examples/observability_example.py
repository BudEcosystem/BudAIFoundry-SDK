#!/usr/bin/env python3
"""AI assistant example with observability.

Shows how a client app uses the Bud SDK with tracing and metrics enabled.
One-line setup, then every inference call is automatically traced.

Metrics follow OTel GenAI Semantic Conventions:
- gen_ai.client.operation.duration  (Histogram, seconds)
- gen_ai.client.token.usage         (Histogram, tokens)
- gen_ai.client.active_requests     (UpDownCounter)

Usage:
    BUD_API_KEY=your-key python examples/observability_example.py
"""

from __future__ import annotations

import os
import time

from bud import BudClient
from bud.observability import (
    TracedStream,
    configure,
    create_traced_span,
    get_meter,
    get_tracer,
    shutdown,
)

BASE_URL = os.environ.get("BUD_BASE_URL", "http://localhost:56054")
API_KEY = os.environ.get("BUD_API_KEY", "my-test-api-key")
OTEL_ENDPOINT = os.environ.get("BUD_OTEL_ENDPOINT", "http://localhost:56056")

# Shared tracer, meter, and instruments — initialised in init_telemetry().
tracer = None
meter = None
duration_histogram = None
token_histogram = None
active_counter = None


def init_telemetry() -> None:
    """Create tracer, meter, and instruments. Call once after configure()."""
    global tracer, meter, duration_histogram, token_histogram, active_counter
    tracer = get_tracer("my-assistant")
    meter = get_meter("my-assistant")
    duration_histogram = meter.create_histogram(
        "gen_ai.client.operation.duration",
        description="GenAI operation duration",
        unit="s",
    )
    token_histogram = meter.create_histogram(
        "gen_ai.client.token.usage",
        description="Tokens consumed per request",
        unit="{token}",
    )
    active_counter = meter.create_up_down_counter(
        "gen_ai.client.active_requests",
        description="Number of active GenAI requests",
        unit="{request}",
    )


def ask(client: BudClient, question: str, system_prompt: str = "You are a helpful assistant.") -> str:
    """Non-streaming: ask a question, get a full response."""
    with tracer.start_as_current_span("ask") as span:
        span.set_attribute("question", question)

        attrs = {
            "gen_ai.operation.name": "chat",
            "gen_ai.request.model": "gpt",
        }
        active_counter.add(1, attrs)
        start = time.monotonic()
        try:
            response = client.chat.completions.create(
                model="gpt",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question},
                ],
                temperature=0.3,
                max_tokens=256,
            )
            duration_s = time.monotonic() - start

            content = response.choices[0].message.content or ""
            span.set_attribute("response_length", len(content))

            response_attrs = {**attrs, "gen_ai.response.model": response.model}
            duration_histogram.record(duration_s, response_attrs)

            if response.usage:
                span.set_attribute("tokens", response.usage.total_tokens)
                token_histogram.record(
                    response.usage.prompt_tokens,
                    {**response_attrs, "gen_ai.token.type": "input"},
                )
                token_histogram.record(
                    response.usage.completion_tokens,
                    {**response_attrs, "gen_ai.token.type": "output"},
                )

            return content
        finally:
            active_counter.add(-1, attrs)


def ask_streaming(
    client: BudClient,
    question: str,
    system_prompt: str = "You are a helpful assistant.",
) -> TracedStream:
    """Streaming: ask a question, yield chunks. TracedStream records TTFT automatically."""
    span, token = create_traced_span(
        "ask-stream",
        tracer,
        attributes={"question": question},
    )

    attrs = {
        "gen_ai.operation.name": "chat",
        "gen_ai.request.model": "gpt",
    }
    active_counter.add(1, attrs)

    raw = client.chat.completions.create(
        model="gpt",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        stream=True,
        temperature=0.3,
        max_tokens=256,
    )

    # TracedStream handles span timing; active_requests decremented after iteration.
    # Duration metric is omitted for streaming (no final usage stats in chunks).
    return TracedStream(raw, span, token)


def main() -> None:
    if not API_KEY:
        print("Error: BUD_API_KEY environment variable is not set.")
        print("Usage: BUD_API_KEY=your-key python examples/observability_example.py")
        exit(1)

    # One-line observability setup — handles providers, exporters, propagators.
    configure(service_name="my-assistant", collector_endpoint=OTEL_ENDPOINT)

    client = BudClient(api_key=API_KEY, base_url=BASE_URL)
    init_telemetry()

    try:
        # Non-streaming call
        print("Q: What is the capital of France?")
        answer = ask(client, "What is the capital of France?")
        print(f"A: {answer}\n")

        # Streaming call
        print("Q: Explain quantum computing in simple terms.")
        print("A: ", end="", flush=True)
        for chunk in ask_streaming(client, "Explain quantum computing in simple terms."):
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                print(delta, end="", flush=True)
        print("\n")

    finally:
        client.close()
        shutdown()

    print("Done. Check your collector (Jaeger, Grafana) for traces.")


if __name__ == "__main__":
    main()
