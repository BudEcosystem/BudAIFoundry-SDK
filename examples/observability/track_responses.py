#!/usr/bin/env python3
"""Demonstrate ``track_responses()`` for automatic Responses API tracing.

Shows six usage patterns:
1. Basic non-streaming traced call (defaults capture ALL fields)
2. Streaming traced call with TTFT measurement
3. Error handling (bad prompt → exception recorded on span)
4. Explicit field selection via ``capture_input`` / ``capture_output``
5. Nesting with the ``@track`` decorator (parent-child spans)
6. Capture nothing (``capture_input=False, capture_output=False``) with custom ``span_name``

Usage:
    BUD_API_KEY=your-key python examples/observability/track_responses.py
"""

from __future__ import annotations

import os

from bud import BudClient
from bud.observability import configure, flush, shutdown, track, track_responses

BASE_URL = os.environ.get("BUD_BASE_URL", "http://localhost:56054")
API_KEY = os.environ.get("BUD_API_KEY", "my-test-api-key")


def example_1_non_streaming(client: BudClient) -> None:
    """Basic non-streaming Responses API call. Defaults capture ALL fields."""
    print("--- Example 1: Non-streaming ---")
    response = client.responses.create(
        prompt={"id": "test_prompt", "variables": {}, "version": "1"},
        input="Hello world",
    )
    # Span name: "responses"
    # Attributes include: bud.inference.request.prompt, bud.inference.request.input,
    #   gen_ai.usage.input_tokens, gen_ai.usage.total_tokens,
    #   gen_ai.response.id, bud.inference.response.output_text
    # All fields captured by default (True = capture everything)
    print(f"  Response: {response.output_text}")


def example_2_streaming(client: BudClient) -> None:
    """Streaming call. Records TTFT, chunk count, and stream_completed."""
    print("--- Example 2: Streaming ---")
    stream = client.responses.create(
        prompt={"id": "test_prompt_stream", "variables": {}, "version": "1"},
        input="Hello world",
        stream=True,
    )
    # Span name: "responses.stream"
    # Attributes: bud.inference.ttft_ms, bud.inference.chunks, bud.inference.stream_completed
    chunks = []
    for event in stream:
        if event.type == "response.output_text.delta":
            chunks.append(event.delta)
    print(f"  Response: {''.join(chunks)}")
    # After full iteration, the completed_response is available with usage data
    completed = stream.completed_response
    if completed is not None:
        print(f"  Usage: {completed.usage}")


def example_3_error_handling(client: BudClient) -> None:
    """Error case: bad prompt ID triggers an API error."""
    print("--- Example 3: Error handling ---")
    try:
        client.responses.create(
            prompt={"id": "nonexistent_prompt", "variables": {}, "version": "1"},
            input="test",
        )
    except Exception as exc:
        # Span status: ERROR, exception recorded on span, re-raised to caller
        print(f"  Expected error: {exc!r}")


def example_4_field_selection() -> None:
    """Explicit field selection to capture only specific fields."""
    print("--- Example 4: Explicit field selection ---")
    selective_client = BudClient(api_key=API_KEY, base_url=BASE_URL)
    track_responses(
        selective_client,
        capture_input=["prompt", "input"],  # Only capture prompt and input
        capture_output=["usage", "output"],  # Only capture usage and output_text
    )
    try:
        response = selective_client.responses.create(
            prompt={"id": "test_prompt", "variables": {}, "version": "1"},
            input="Hello!",
        )
        # Span has bud.inference.request.prompt AND bud.inference.response.output_text
        print(f"  Response: {response.output_text}")
    finally:
        selective_client.close()


@track(name="pipeline", type="chain")
def example_5_nesting(client: BudClient) -> str:
    """Nesting: @track creates a parent span, responses.create() is a child span."""
    print("--- Example 5: Nesting with @track ---")
    response = client.responses.create(
        prompt={"id": "test_prompt", "variables": {}, "version": "1"},
        input="Explain nesting in one sentence",
    )
    output = response.output_text or ""
    # Trace tree:
    #   pipeline (parent, from @track)
    #     └── responses (child, from track_responses)
    print(f"  Response: {output}")
    return output


def example_6_capture_nothing() -> None:
    """Capture nothing: span-only mode with no request/response attributes."""
    print("--- Example 6: Capture nothing (span_name='silent-responses') ---")
    silent_client = BudClient(api_key=API_KEY, base_url=BASE_URL)
    track_responses(
        silent_client,
        capture_input=False,
        capture_output=False,
        span_name="silent-responses",
    )
    try:
        response = silent_client.responses.create(
            prompt={"id": "test_prompt", "variables": {}, "version": "1"},
            input="Ping",
        )
        # Span name: "silent-responses"
        # Only always-on attributes: gen_ai.system, bud.inference.operation, bud.inference.stream
        # NO bud.inference.request.*, NO gen_ai.usage.*, NO gen_ai.response.*
        print(f"  Response: {response.output_text}")
    finally:
        silent_client.close()


def main() -> None:
    client = BudClient(api_key=API_KEY, base_url=BASE_URL)
    configure(client=client, service_name="track-responses-example")
    track_responses(client)

    try:
        example_1_non_streaming(client)
        example_2_streaming(client)
        example_3_error_handling(client)
        example_4_field_selection()
        example_5_nesting(client)
        example_6_capture_nothing()
    finally:
        client.close()
        flush(timeout_millis=60000)
        shutdown()

    print("\nDone. Check your collector for traces.")


if __name__ == "__main__":
    main()
