#!/usr/bin/env python3
"""AI assistant example with @track decorator — non-streaming and streaming.

Shows how @track replaces manual span management and TracedStream for both
call styles.  For the simplest @track usage, see track_example.py.

Usage:
    BUD_API_KEY=your-key python examples/observability_example.py
"""

from __future__ import annotations

import os

from bud import BudClient
from bud.observability import configure, shutdown, track

BASE_URL = os.environ.get("BUD_BASE_URL", "http://localhost:56054")
API_KEY = os.environ.get("BUD_API_KEY", "my-test-api-key")
OTEL_ENDPOINT = os.environ.get("BUD_OTEL_ENDPOINT", "http://localhost:56056")


@track(name="ask", type="llm", ignore_arguments=["client"])
def ask(
    client: BudClient, question: str, system_prompt: str = "You are a helpful assistant."
) -> str:
    """Non-streaming: ask a question, get a full response."""
    response = client.chat.completions.create(
        model="gpt",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        temperature=0.3,
        max_tokens=256,
    )
    return response.choices[0].message.content or ""


@track(name="ask-stream", type="llm", ignore_arguments=["client"])
def ask_streaming(
    client: BudClient, question: str, system_prompt: str = "You are a helpful assistant."
):
    """Streaming: ask a question, yield chunks. The @track generator wrapper keeps the span open."""
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
    yield from raw


def main() -> None:
    configure(service_name="my-assistant", collector_endpoint=OTEL_ENDPOINT)
    client = BudClient(api_key=API_KEY, base_url=BASE_URL)

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
