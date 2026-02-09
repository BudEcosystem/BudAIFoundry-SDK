#!/usr/bin/env python3
"""Simplified AI assistant example using the @track decorator.

Compare with observability_example.py which uses manual span management.
The @track decorator reduces per-function boilerplate from ~15 lines to 1 line.

Usage:
    BUD_API_KEY=your-key python examples/track_example.py
"""

from __future__ import annotations

import os

from bud import BudClient
from bud.observability import configure, shutdown, track

BASE_URL = os.environ.get("BUD_BASE_URL", "http://localhost:56054")
API_KEY = os.environ.get("BUD_API_KEY", "my-test-api-key")
OTEL_ENDPOINT = os.environ.get("BUD_OTEL_ENDPOINT", "http://localhost:56056")


@track(name="ask-question", type="llm")
def ask(client: BudClient, question: str) -> str:
    """Ask a question and return the response. Automatically traced."""
    response = client.chat.completions.create(
        model="gpt",
        messages=[{"role": "user", "content": question}],
        temperature=0.3,
        max_tokens=256,
    )
    return response.choices[0].message.content or ""


@track(name="pipeline", type="chain")
def pipeline(client: BudClient) -> dict[str, str]:
    """Multi-step pipeline. Each @track call nests as a child span."""
    summary = ask(client, "Summarize quantum computing in one sentence.")
    followup = ask(client, f"Explain this further: {summary}")
    return {"summary": summary, "followup": followup}


def main() -> None:
    configure(service_name="track-example-resource", collector_endpoint=OTEL_ENDPOINT)
    client = BudClient(api_key=API_KEY, base_url=BASE_URL)

    try:
        result = pipeline(client)
        print(f"Summary:  {result['summary']}")
        print(f"Followup: {result['followup']}")
    finally:
        client.close()
        shutdown()

    print("\nDone. Check your collector for traces:")
    print("  pipeline (root)")
    print("    -> ask (child, question='Summarize...')")
    print("    -> ask (child, question='Explain...')")


if __name__ == "__main__":
    main()
