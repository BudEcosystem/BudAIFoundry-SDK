#!/usr/bin/env python3
"""Real-world @track decorator examples — non-streaming scenarios.

Demonstrates every @track parameter through a document analysis pipeline:
- Bare @track, named spans, type annotations
- ignore_arguments to exclude non-serializable objects
- capture_input/capture_output toggling
- Dict vs scalar output capture
- Static attributes
- Nested parent-child spans
- Error recording and propagation
- self/cls auto-skipping on class methods
- Async function support
- Thread safety with ThreadPoolExecutor context propagation

Usage:
    BUD_API_KEY=your-key python examples/observability/track_non_streaming.py
"""

from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

from opentelemetry import context as otel_context

from bud import BudClient
from bud.observability import configure, shutdown, track

BASE_URL = os.environ.get("BUD_BASE_URL", "http://localhost:56054")
API_KEY = os.environ.get("BUD_API_KEY", "my-test-api-key")


# ---------------------------------------------------------------------------
# 1. Bare @track — simplest usage, auto-names span from __qualname__
# ---------------------------------------------------------------------------


@track
def format_result(summary: str, sentiment: str, dimensions: int) -> str:
    """Format analysis results into a single string.

    Span name = 'format_result' (auto-derived from function qualname).
    All three arguments are captured as bud.track.input.summary, etc.
    Return value captured as bud.track.output (scalar string).
    """
    return f"[{sentiment.upper()}] {summary} (embedding: {dimensions}d)"


# ---------------------------------------------------------------------------
# 2. Static attributes — attach metadata to every invocation
# ---------------------------------------------------------------------------


@track(name="audit-log", attributes={"service": "doc-analyzer", "version": "1.0"})
def log_audit(action: str, document_preview: str) -> dict[str, str]:
    """Log an audit entry with static span attributes.

    Every invocation of this function will have service='doc-analyzer' and
    version='1.0' as span attributes, in addition to the captured inputs.
    Returns dict → bud.track.output.action, bud.track.output.preview.
    """
    return {"action": action, "preview": document_preview[:50]}


# ---------------------------------------------------------------------------
# 3. Class with @track methods — self is auto-skipped
# ---------------------------------------------------------------------------


class DocumentAnalyzer:
    """Analyzes documents using classification, embeddings, and LLM summarization.

    All methods use @track. The ``self`` parameter is automatically excluded
    from span input attributes (the decorator skips 'self' and 'cls').
    """

    def __init__(self, client: BudClient) -> None:
        self.client = client

    # 3a. type="tool" — classification (dummy logic), returns scalar
    @track(name="classify", type="tool")
    def classify(self, text: str) -> str:
        """Classify sentiment of the given text.

        Returns a scalar string → captured as bud.track.output = "'positive'".
        ``self`` is auto-skipped; only ``text`` appears in bud.track.input.*.
        """
        # Simple keyword-based sentiment for demonstration purposes.
        lower = text.lower()
        if any(w in lower for w in ("exceeded", "strong", "improved", "growth")):
            return "positive"
        if any(w in lower for w in ("declined", "loss", "failed", "weak")):
            return "negative"
        return "neutral"

    # 3b. capture_output=False — embedding (dummy vector)
    @track(name="embed", type="tool", capture_output=False)
    def embed(self, text: str) -> list[float]:
        """Generate a dummy embedding vector for the given text.

        capture_output=False prevents the float list from being recorded on the
        span — demonstrates suppressing large outputs to keep traces lightweight.
        In production you'd call a real embedding model here.
        """
        # Deterministic dummy vector derived from text length.
        n = len(text)
        return [round((((n * (i + 1) * 7) % 200) - 100) / 100.0, 4) for i in range(8)]

    # 3c. type="llm" with model info in static attributes
    @track(
        name="summarize",
        type="llm",
        attributes={"model.name": "gpt"},
    )
    def summarize(self, text: str, max_words: int = 50) -> str:
        """Summarize text via LLM.

        Both ``text`` and ``max_words`` are captured as inputs (self is skipped).
        Static attribute model.name='gpt' appears on every span.
        Long text values are auto-truncated to 1000 chars by the decorator.
        """
        response = self.client.chat.completions.create(
            model="gpt",
            messages=[
                {"role": "system", "content": f"Summarize in under {max_words} words."},
                {"role": "user", "content": text},
            ],
            temperature=0.3,
            max_tokens=200,
        )
        return response.choices[0].message.content or ""

    # 3d. type="chain" — pipeline orchestrator, capture_input=False, dict return
    @track(name="analyze-document", type="chain", capture_input=False)
    def analyze(self, text: str) -> dict[str, str | int]:
        """Full analysis pipeline — classify, embed, and summarize.

        capture_input=False avoids recording the (potentially long) text on the
        parent span; child spans already capture their own inputs.
        Returns dict → bud.track.output.summary, bud.track.output.sentiment,
        bud.track.output.embedding_dims as separate span attributes.
        Child spans (classify, embed, summarize) nest under this parent.
        """
        sentiment = self.classify(text)
        embedding = self.embed(text)
        summary = self.summarize(text)
        return {
            "summary": summary,
            "sentiment": sentiment,
            "embedding_dims": len(embedding),
        }

    # 3e. Thread-safe parallel analysis with OTel context propagation
    @track(name="analyze-parallel", type="chain", capture_input=False)
    def analyze_parallel(self, text: str) -> dict[str, str | int]:
        """Same as analyze() but runs classify and embed concurrently in threads.

        Captures the current OTel context and passes it to each worker thread
        via _run_with_context so child spans nest under this parent span.
        Without context propagation, the thread spans would be orphaned roots.
        """
        ctx = otel_context.get_current()
        with ThreadPoolExecutor(max_workers=2) as pool:
            sentiment_future = pool.submit(_run_with_context, ctx, self.classify, text)
            embed_future = pool.submit(_run_with_context, ctx, self.embed, text)
            sentiment = sentiment_future.result()
            embedding = embed_future.result()
        summary = self.summarize(text)
        return {
            "summary": summary,
            "sentiment": sentiment,
            "embedding_dims": len(embedding),
        }


# ---------------------------------------------------------------------------
# 4. Async function — @track works identically on async
# ---------------------------------------------------------------------------


@track(name="async-summarize", type="llm", ignore_arguments=["client"])
async def async_summarize(client: BudClient, text: str) -> str:
    """Async LLM call. @track detects async and wraps with an async span.

    ignore_arguments=["client"] excludes the non-serializable client object.
    Only ``text`` appears in bud.track.input.*.
    """
    # BudClient is sync; in production you'd use an async HTTP client.
    response = client.chat.completions.create(
        model="gpt",
        messages=[{"role": "user", "content": f"Summarize: {text}"}],
        temperature=0.3,
        max_tokens=100,
    )
    return response.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# 5. Error handling — @track records exceptions on span, re-raises
# ---------------------------------------------------------------------------


@track(name="bad-model-call", type="llm", ignore_arguments=["client"])
def ask_with_bad_model(client: BudClient, question: str) -> str:
    """Deliberately uses an invalid model to show error recording.

    The span will have:
    - status = ERROR
    - exception event with stack trace
    - bud.track.input.question captured before the error occurs
    The exception is re-raised after being recorded.
    """
    response = client.chat.completions.create(
        model="nonexistent-model-xyz",
        messages=[{"role": "user", "content": question}],
    )
    return response.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# 6. Thread safety — propagating OTel context to worker threads
# ---------------------------------------------------------------------------


def _run_with_context(ctx: otel_context.Context, fn, *args):
    """Run a function in a worker thread with the parent's OTel context.

    ThreadPoolExecutor doesn't propagate contextvars, so child spans created
    in worker threads become orphaned root spans. Attaching the parent context
    before calling the function restores the parent-child relationship.
    """
    token = otel_context.attach(ctx)
    try:
        return fn(*args)
    finally:
        otel_context.detach(token)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    client = BudClient(api_key=API_KEY, base_url=BASE_URL)
    configure(client=client, service_name="doc-analyzer")

    try:
        # --- Example 1: Full pipeline (nested spans) ---
        print("=" * 60)
        print("Example 1: Document Analysis Pipeline (nested spans)")
        print("=" * 60)
        analyzer = DocumentAnalyzer(client)
        text = (
            "The quarterly earnings exceeded expectations with a 15% increase "
            "in revenue driven by strong demand for cloud AI services. Operating "
            "margins improved to 28%, and the company raised full-year guidance."
        )
        result = analyzer.analyze(text)
        print(f"Sentiment:  {result['sentiment']}")
        print(f"Summary:    {result['summary']}")
        print(f"Embed dims: {result['embedding_dims']}")
        print()

        # --- Example 2: Bare @track utility ---
        print("=" * 60)
        print("Example 2: Bare @track (auto span name)")
        print("=" * 60)
        formatted = format_result(
            str(result["summary"]), str(result["sentiment"]), int(result["embedding_dims"])
        )
        print(f"Formatted: {formatted}")
        print()

        # --- Example 3: Static attributes ---
        print("=" * 60)
        print("Example 3: Static attributes on span")
        print("=" * 60)
        audit = log_audit("analyze", text)
        print(f"Audit: {audit}")
        print()

        # --- Example 4: Async function ---
        print("=" * 60)
        print("Example 4: Async @track")
        print("=" * 60)
        async_result = asyncio.run(async_summarize(client, text))
        print(f"Async summary: {async_result}")
        print()

        # --- Example 5: Error handling ---
        print("=" * 60)
        print("Example 5: Error recording (bad model)")
        print("=" * 60)
        try:
            ask_with_bad_model(client, "Will this work?")
        except Exception as e:
            print(f"Expected error: {type(e).__name__}: {e}")
            print("(Span recorded ERROR status + exception event)")
        print()

        # --- Example 6: Thread safety (context propagation) ---
        print("=" * 60)
        print("Example 6: Thread-safe @track (parallel with context)")
        print("=" * 60)
        parallel_result = analyzer.analyze_parallel(text)
        print(f"Sentiment:  {parallel_result['sentiment']}")
        print(f"Summary:    {parallel_result['summary']}")
        print(f"Embed dims: {parallel_result['embedding_dims']}")
        print()

    finally:
        client.close()
        shutdown()

    print("Done. Expected trace structure:")
    print("  analyze-document (root, type=chain)")
    print("    -> classify (child, type=tool)")
    print("    -> embed (child, type=tool, no output)")
    print("    -> summarize (child, type=llm)")
    print("  format_result (root, bare @track)")
    print("  audit-log (root, static attrs: service, version)")
    print("  async-summarize (root, type=llm)")
    print("  bad-model-call (root, type=llm, status=ERROR)")
    print("  analyze-parallel (root, type=chain)")
    print("    -> classify (child, type=tool)         # thread 1, context propagated")
    print("    -> embed (child, type=tool, no output)  # thread 2, context propagated")
    print("    -> summarize (child, type=llm)")


if __name__ == "__main__":
    if not API_KEY:
        print("Error: BUD_API_KEY environment variable is not set.")
        print("Usage: BUD_API_KEY=your-key python examples/observability/track_non_streaming.py")
        raise SystemExit(1)
    main()
