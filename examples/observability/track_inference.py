#!/usr/bin/env python3
"""Demonstrate ``track_chat_completions()`` for automatic inference tracing.

Shows six usage patterns:
1. Basic non-streaming traced call (defaults capture ALL fields including messages/content)
2. Streaming traced call with TTFT measurement
3. Error handling (bad model → exception recorded on span)
4. Explicit field selection via ``capture_input=["model", "messages"]``
5. Nesting with the ``@track`` decorator (parent-child spans)
6. Capture nothing (``capture_input=False, capture_output=False``) with custom ``span_name``

Usage:
    BUD_API_KEY=your-key python examples/observability/track_inference.py
"""

from __future__ import annotations

import os

from bud import BudClient
from bud.observability import configure, shutdown, track, track_chat_completions

BASE_URL = os.environ.get("BUD_BASE_URL", "http://localhost:56054")
API_KEY = os.environ.get("BUD_API_KEY", "my-test-api-key")
OTEL_ENDPOINT = os.environ.get("BUD_OTEL_ENDPOINT", "http://localhost:56054")


def example_1_non_streaming(client: BudClient) -> None:
    """Basic non-streaming call. Defaults capture ALL fields including messages and content."""
    print("--- Example 1: Non-streaming ---")
    response = client.chat.completions.create(
        model="gpt",
        messages=[{"role": "user", "content": "What is 2+2?"}],
    )
    # Span name: "chat"
    # Attributes include: gen_ai.request.model, gen_ai.content.prompt,
    #   gen_ai.usage.input_tokens, gen_ai.usage.total_tokens,
    #   gen_ai.response.object, bud.inference.response.choices (JSON blob with
    #   content, finish_reason, tool_calls per choice)
    # All fields captured by default (True = capture everything)
    print(f"  Response: {response.choices[0].message.content}")


def example_2_streaming(client: BudClient) -> None:
    """Streaming call. Records TTFT, chunk count, and stream_completed."""
    print("--- Example 2: Streaming ---")
    stream = client.chat.completions.create(
        model="gpt",
        messages=[{"role": "user", "content": "Count to 5"}],
        stream=True,
    )
    # Span name: "chat.stream"
    # Attributes: bud.inference.ttft_ms, bud.inference.chunks, bud.inference.stream_completed
    chunks = []
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            chunks.append(chunk.choices[0].delta.content)
    print(f"  Response: {''.join(chunks)}")


def example_3_error_handling(client: BudClient) -> None:
    """Error case: bad model name triggers an API error."""
    print("--- Example 3: Error handling ---")
    try:
        client.chat.completions.create(
            model="nonexistent-model-xyz",
            messages=[{"role": "user", "content": "test"}],
        )
    except Exception as exc:
        # Span status: ERROR, exception recorded on span, re-raised to caller
        print(f"  Expected error: {exc!r}")


def example_4_pii_optin() -> None:
    """Explicit field selection to capture only specific fields."""
    print("--- Example 4: Explicit field selection ---")
    pii_client = BudClient(api_key=API_KEY, base_url=BASE_URL)
    track_chat_completions(
        pii_client,
        capture_input=["model", "messages"],  # Only capture model and messages
        capture_output=["usage", "choices"],  # Only capture usage and choices
    )
    try:
        response = pii_client.chat.completions.create(
            model="gpt",
            messages=[{"role": "user", "content": "Hello!"}],
        )
        # Span has gen_ai.content.prompt AND bud.inference.response.choices
        print(f"  Response (with PII): {response.choices[0].message.content}")
    finally:
        pii_client.close()


@track(name="pipeline", type="chain")
def example_5_nesting(client: BudClient) -> str:
    """Nesting: @track creates a parent span, chat create() is a child span."""
    print("--- Example 5: Nesting with @track ---")
    response = client.chat.completions.create(
        model="gpt",
        messages=[{"role": "user", "content": "Explain nesting in one sentence"}],
    )
    content = response.choices[0].message.content or ""
    # Trace tree:
    #   pipeline (parent, from @track)
    #     └── chat (child, from track_chat_completions)
    print(f"  Response: {content}")
    return content


def example_6_capture_nothing() -> None:
    """Capture nothing: span-only mode with no request/response attributes."""
    print("--- Example 6: Capture nothing (span_name='silent-chat') ---")
    silent_client = BudClient(api_key=API_KEY, base_url=BASE_URL)
    track_chat_completions(
        silent_client,
        capture_input=False,
        capture_output=False,
        span_name="silent-chat",
    )
    try:
        response = silent_client.chat.completions.create(
            model="gpt",
            messages=[{"role": "user", "content": "Ping"}],
        )
        # Span name: "silent-chat"
        # Only always-on attributes: gen_ai.system, bud.inference.operation, bud.inference.stream
        # NO gen_ai.request.model, NO gen_ai.usage.*, NO gen_ai.response.*
        print(f"  Response: {response.choices[0].message.content}")
    finally:
        silent_client.close()


def main() -> None:
    configure(service_name="track-inference-example", collector_endpoint=OTEL_ENDPOINT, api_key="my-test-api-key")

    client = BudClient(api_key=API_KEY, base_url=BASE_URL)
    track_chat_completions(client)

    try:
        example_1_non_streaming(client)
        example_2_streaming(client)
        example_3_error_handling(client)
        example_4_pii_optin()
        example_5_nesting(client)
        example_6_capture_nothing()
    finally:
        client.close()
        shutdown()

    print("\nDone. Check your collector for traces.")


if __name__ == "__main__":
    main()
