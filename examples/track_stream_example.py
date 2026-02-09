#!/usr/bin/env python3
"""Pipeline example combining non-streaming and streaming calls with @track.

Demonstrates:
- @track on a sync function (non-streaming LLM call)
- @track on a sync generator (streaming LLM call, span stays open across yields)
- @track on a pipeline that nests child spans
- ignore_arguments to exclude certain inputs from capture
- capture_input=False when no useful inputs exist

Usage:
    BUD_API_KEY=your-key python examples/track_stream_example.py
"""

from __future__ import annotations

import os
from collections.abc import Iterator

from bud import BudClient
from bud.observability import configure, shutdown, track

BASE_URL = os.environ.get("BUD_BASE_URL", "http://localhost:56054")
API_KEY = os.environ.get("BUD_API_KEY", "my-test-api-key")
OTEL_ENDPOINT = os.environ.get("BUD_OTEL_ENDPOINT", "http://localhost:56056")


@track(name="ask", type="llm", ignore_arguments=["client"])
def ask(client: BudClient, question: str) -> str:
    """Non-streaming LLM call. The ``client`` arg is excluded from span attributes."""
    response = client.chat.completions.create(
        model="gpt",
        messages=[{"role": "user", "content": question}],
        temperature=0.3,
        max_tokens=256,
    )
    return response.choices[0].message.content or ""


@track(name="ask-stream", type="llm", ignore_arguments=["client"])
def ask_streaming(client: BudClient, question: str) -> Iterator:
    """Streaming LLM call. The span stays open until the generator is exhausted
    and records ``bud.track.yield_count`` with the number of chunks yielded."""
    stream = client.chat.completions.create(
        model="gpt",
        messages=[{"role": "user", "content": question}],
        stream=True,
        temperature=0.3,
        max_tokens=256,
    )
    yield from stream


@track(name="pipeline", type="chain", capture_input=False)
def pipeline(client: BudClient) -> dict[str, str]:
    """Multi-step pipeline. ``capture_input=False`` avoids recording the client object.

    Child spans (ask, ask-stream) nest automatically under this root span.
    """
    summary = ask(client, "Summarize quantum computing in one sentence.")

    # Consume the streaming generator, printing chunks as they arrive.
    # Reasoning models may send text via `reasoning_content` instead of `content`.
    print("Followup (streaming): ", end="", flush=True)
    chunks: list[str] = []
    for chunk in ask_streaming(client, f"Explain this further: {summary}"):
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        text = delta.content or delta.reasoning_content
        if text:
            print(text, end="", flush=True)
            chunks.append(text)
    print()
    followup = "".join(chunks)

    return {"summary": summary, "followup": followup}


def main() -> None:
    configure(service_name="track-stream-example", collector_endpoint=OTEL_ENDPOINT)
    client = BudClient(api_key=API_KEY, base_url=BASE_URL)

    try:
        result = pipeline(client)
        print(f"\nSummary:  {result['summary']}")
    finally:
        client.close()
        shutdown()

    print("\nDone. Expected trace structure:")
    print("  pipeline (root, type=chain)")
    print("    -> ask (child, type=llm)")
    print("    -> ask-stream (child, type=llm, bud.track.yield_count=N)")


if __name__ == "__main__":
    main()
