#!/usr/bin/env python3
"""Real-world @track decorator examples — streaming scenarios.

Demonstrates every streaming-specific @track behavior through various patterns:
- Basic sync generator with LLM streaming
- capture_output=False for large streams
- Custom generations_aggregator for raw chunk objects
- Simple string generator with built-in aggregation
- Class methods mixing streaming + non-streaming children
- Thread-safe parallel streaming with OTel context propagation
- Partial consumption / early break
- Async generator support
- Error mid-stream recording

Usage:
    BUD_API_KEY=your-key python examples/observability/track_streaming.py
"""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import AsyncIterator, Iterator
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from opentelemetry import context as otel_context

from bud import BudClient
from bud.observability import configure, shutdown, track

BASE_URL = os.environ.get("BUD_BASE_URL", "http://localhost:56054")
API_KEY = os.environ.get("BUD_API_KEY", "my-test-api-key")

# Higher token budget so reasoning models finish their thinking phase and
# produce actual content tokens.  Reasoning models (e.g. DeepSeek-R1) first
# stream ``delta.reasoning_content`` chunks, then ``delta.content`` chunks.
_LLM_MAX_TOKENS = 500


def _extract_text(chunk: Any) -> str | None:
    """Extract text from a streaming chunk, handling reasoning models.

    Reasoning models stream ``delta.reasoning_content`` during the thinking
    phase and ``delta.content`` during the answer phase.  We yield both so
    the example always produces output regardless of model type.
    """
    if not chunk.choices:
        return None
    delta = chunk.choices[0].delta
    return delta.content or delta.reasoning_content or None


# ---------------------------------------------------------------------------
# 1. Basic streaming LLM call (sync generator)
# ---------------------------------------------------------------------------


@track(name="stream-response", type="llm", ignore_arguments=["client"])
def stream_response(client: BudClient, prompt: str) -> Iterator[str]:
    """Stream an LLM response, yielding text chunks.

    The span stays open for the entire iteration. When the generator completes:
    - bud.track.yield_count = number of chunks yielded
    - bud.track.generator_completed = True
    - bud.track.output = all string chunks auto-joined into one string
    """
    stream = client.chat.completions.create(
        model="gpt",
        messages=[{"role": "user", "content": prompt}],
        stream=True,
        max_tokens=_LLM_MAX_TOKENS,
    )
    for chunk in stream:
        text = _extract_text(chunk)
        if text:
            yield text


# ---------------------------------------------------------------------------
# 2. Streaming with capture_output=False
# ---------------------------------------------------------------------------


@track(name="stream-no-output", type="llm", capture_output=False, ignore_arguments=["client"])
def stream_no_output(client: BudClient, prompt: str) -> Iterator[str]:
    """Stream LLM response but suppress output capture.

    Useful for very large streams where recording full output is wasteful.
    yield_count and generator_completed are still recorded, but
    bud.track.output is NOT set on the span.
    """
    stream = client.chat.completions.create(
        model="gpt",
        messages=[{"role": "user", "content": prompt}],
        stream=True,
        max_tokens=_LLM_MAX_TOKENS,
    )
    for chunk in stream:
        text = _extract_text(chunk)
        if text:
            yield text


# ---------------------------------------------------------------------------
# 3. Custom generations_aggregator
# ---------------------------------------------------------------------------


def aggregate_chunks(chunks: list[Any]) -> dict[str, Any]:
    """Custom aggregator that extracts text from ChatCompletionChunk objects.

    Extracts both ``delta.content`` and ``delta.reasoning_content`` to handle
    reasoning models.  Captures the final finish_reason.
    This is passed to @track via generations_aggregator= so the decorator
    stores a structured dict as bud.track.output instead of a list repr.
    """
    texts: list[str] = []
    finish_reason: str | None = None
    for chunk in chunks:
        if hasattr(chunk, "choices") and chunk.choices:
            choice = chunk.choices[0]
            if hasattr(choice, "delta"):
                text = _extract_text(chunk)
                if text:
                    texts.append(text)
            if hasattr(choice, "finish_reason") and choice.finish_reason:
                finish_reason = choice.finish_reason
    return {
        "text": "".join(texts),
        "finish_reason": finish_reason,
        "chunk_count": len(chunks),
    }


@track(
    name="stream-raw-chunks",
    type="llm",
    generations_aggregator=aggregate_chunks,
    ignore_arguments=["client"],
)
def stream_raw_chunks(client: BudClient, prompt: str) -> Iterator[Any]:
    """Yield raw ChatCompletionChunk objects (not extracted text).

    The custom aggregate_chunks function turns the raw chunk list into a
    structured dict with text, finish_reason, and chunk_count.
    Uses ``yield from`` to pass through the stream object directly.
    """
    stream = client.chat.completions.create(
        model="gpt",
        messages=[{"role": "user", "content": prompt}],
        stream=True,
        max_tokens=_LLM_MAX_TOKENS,
    )
    yield from stream


# ---------------------------------------------------------------------------
# 4. Simple string generator (no LLM, built-in aggregation)
# ---------------------------------------------------------------------------


@track(name="word-stream", type="tool")
def stream_words(sentence: str) -> Iterator[str]:
    """Yield individual words from a sentence with a small delay.

    Demonstrates that @track works with any generator, not just LLM streams.
    Built-in aggregation joins all yielded strings directly (no separator):
    bud.track.output = "Thequickbrownfox..." (designed for LLM token chunks).
    """
    for word in sentence.split():
        time.sleep(0.01)
        yield word


# ---------------------------------------------------------------------------
# 5. StreamAnalyzer class with streaming methods
# ---------------------------------------------------------------------------


class StreamAnalyzer:
    """Analyzes text using a mix of streaming and non-streaming methods.

    Demonstrates:
    - self auto-skipping on class methods (same as non-streaming)
    - Streaming child spans nested under a chain parent
    - Thread-safe parallel execution consuming generators within context
    """

    def __init__(self, client: BudClient) -> None:
        self.client = client

    # 5a. Non-streaming helper — type="tool"
    @track(name="classify", type="tool")
    def classify(self, text: str) -> str:
        """Classify sentiment of the given text.

        Returns a scalar string. ``self`` is auto-skipped.
        """
        lower = text.lower()
        if any(w in lower for w in ("exceeded", "strong", "improved", "growth")):
            return "positive"
        if any(w in lower for w in ("declined", "loss", "failed", "weak")):
            return "negative"
        return "neutral"

    # 5b. Streaming LLM call
    @track(name="stream-summarize", type="llm", attributes={"model.name": "gpt"})
    def stream_summarize(self, text: str) -> Iterator[str]:
        """Stream a summary from the LLM.

        yield_count and output are recorded when the generator completes.
        Static attribute model.name='gpt' is set on every span invocation.
        """
        stream = self.client.chat.completions.create(
            model="gpt",
            messages=[
                {"role": "system", "content": "Summarize in under 30 words."},
                {"role": "user", "content": text},
            ],
            stream=True,
            max_tokens=_LLM_MAX_TOKENS,
        )
        for chunk in stream:
            text_ = _extract_text(chunk)
            if text_:
                yield text_

    # 5c. Chain orchestrator mixing streaming + non-streaming children
    @track(name="stream-analyze", type="chain", capture_input=False)
    def analyze(self, text: str) -> Iterator[str]:
        """Classify then stream a summary.

        capture_input=False avoids recording the potentially long text on
        the parent chain span; child spans capture their own inputs.

        The chain itself is a generator — yields a category prefix,
        then yields from the streaming summarize call.
        Child spans nest under this parent:
          stream-analyze (chain)
            -> classify (tool)
            -> stream-summarize (llm)
        """
        category = self.classify(text)
        yield f"[{category.upper()}] "
        yield from self.stream_summarize(text)

    # 5d. Thread-safe parallel streaming
    @track(name="stream-analyze-parallel", type="chain", capture_input=False)
    def analyze_parallel(self, text: str) -> dict[str, str | list[str]]:
        """Run classify and stream_summarize in parallel threads.

        Returns a dict (NOT a generator) because threads must fully consume
        generators within the attached OTel context scope. A generator return
        would close the thread context before the caller iterates.

        Uses _consume_stream_with_context to attach context AND consume the
        generator within the thread.
        """
        ctx = otel_context.get_current()
        with ThreadPoolExecutor(max_workers=2) as pool:
            classify_future = pool.submit(_run_with_context, ctx, self.classify, text)
            summary_future = pool.submit(
                _consume_stream_with_context, ctx, self.stream_summarize, text
            )
            category = classify_future.result()
            summary_chunks = summary_future.result()
        return {
            "category": category,
            "summary_chunks": summary_chunks,
            "summary": "".join(summary_chunks),
        }


# ---------------------------------------------------------------------------
# 6. Partial consumption / early break
# ---------------------------------------------------------------------------


@track(name="number-stream")
def stream_numbers(count: int) -> Iterator[str]:
    """Yield stringified numbers from 0 to count-1.

    When the consumer breaks early:
    - bud.track.generator_completed = False
    - bud.track.yield_count = number actually consumed
    - bud.track.output = partial output (only consumed items)
    """
    for i in range(count):
        yield str(i)


# ---------------------------------------------------------------------------
# 7. Async generator
# ---------------------------------------------------------------------------


@track(name="async-data-stream", type="tool")
async def async_stream_data(items: list[str]) -> AsyncIterator[str]:
    """Async generator yielding items with simulated async delays.

    Exercises the _wrap_async_generator code path. Uses simulated data
    rather than real LLM streaming because the SDK has sync-only streaming.
    Records yield_count, generator_completed, and auto-joined output.
    """
    for item in items:
        await asyncio.sleep(0.01)
        yield item


async def run_async_example() -> list[str]:
    """Consume the async generator and return collected items."""
    results: list[str] = []
    async for item in async_stream_data(["alpha", "beta", "gamma", "delta"]):
        results.append(item)
    return results


# ---------------------------------------------------------------------------
# 8. Error mid-stream
# ---------------------------------------------------------------------------


@track(name="error-mid-stream", type="llm", ignore_arguments=["client"])
def stream_with_error(client: BudClient, prompt: str, fail_after: int = 3) -> Iterator[str]:
    """Stream real LLM chunks then raise an error after fail_after chunks.

    Demonstrates mid-stream error recording:
    - Partial chunks are yielded successfully before the error
    - Exception is recorded on the span with status=ERROR
    - bud.track.yield_count reflects only the chunks yielded before failure
    - bud.track.output contains partial output (chunks yielded so far)
    - The exception is re-raised to the caller
    """
    stream = client.chat.completions.create(
        model="gpt",
        messages=[{"role": "user", "content": prompt}],
        stream=True,
        max_tokens=_LLM_MAX_TOKENS,
    )
    count = 0
    for chunk in stream:
        text_ = _extract_text(chunk)
        if text_:
            count += 1
            yield text_
            if count >= fail_after:
                raise RuntimeError(f"Simulated mid-stream failure after {count} chunks")


# ---------------------------------------------------------------------------
# 9. Thread safety helpers
# ---------------------------------------------------------------------------


def _run_with_context(ctx: otel_context.Context, fn: Any, *args: Any) -> Any:
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


def _consume_stream_with_context(ctx: otel_context.Context, gen_fn: Any, *args: Any) -> list[str]:
    """Attach OTel context, call a generator function, and fully consume it.

    Critical for thread-safe streaming: the generator's @track span stays
    open until the generator is exhausted. If we returned the generator to
    the main thread, the context would be detached before iteration,
    orphaning the child span. Instead, consume entirely within the thread.
    """
    token = otel_context.attach(ctx)
    try:
        return list(gen_fn(*args))
    finally:
        otel_context.detach(token)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    client = BudClient(api_key=API_KEY, base_url=BASE_URL)
    configure(client=client, service_name="stream-analyzer")

    try:
        # --- Example 1: Basic streaming (yield_count + auto-join) ---
        print("=" * 60)
        print("Example 1: Basic streaming LLM call")
        print("=" * 60)
        chunks: list[str] = []
        for text in stream_response(client, "Explain quantum computing in one sentence."):
            chunks.append(text)
        print(f"Chunks received: {len(chunks)}")
        print(f"Full response: {''.join(chunks)}")
        print()

        # --- Example 2: capture_output=False (large stream) ---
        print("=" * 60)
        print("Example 2: capture_output=False (no output attribute)")
        print("=" * 60)
        chunks = []
        for text in stream_no_output(client, "List five programming languages."):
            chunks.append(text)
        print(f"Chunks received: {len(chunks)}")
        print(f"Full response: {''.join(chunks)}")
        print("(Span has yield_count but no bud.track.output)")
        print()

        # --- Example 3: Custom generations_aggregator (raw chunks) ---
        print("=" * 60)
        print("Example 3: Custom generations_aggregator")
        print("=" * 60)
        raw_count = 0
        for _chunk in stream_raw_chunks(client, "What is machine learning?"):
            raw_count += 1
        print(f"Raw chunks yielded: {raw_count}")
        print("(Span output is aggregated dict with text + finish_reason)")
        print()

        # --- Example 4: String generator (built-in aggregation) ---
        print("=" * 60)
        print("Example 4: Simple string generator")
        print("=" * 60)
        words: list[str] = []
        for word in stream_words("The quick brown fox jumps over the lazy dog"):
            words.append(word)
        print(f"Words yielded: {len(words)}")
        print(f"Joined output: {' '.join(words)}")
        print()

        # --- Example 5a: Chain with streaming child ---
        print("=" * 60)
        print("Example 5a: StreamAnalyzer chain (classify -> stream_summarize)")
        print("=" * 60)
        analyzer = StreamAnalyzer(client)
        text = (
            "The quarterly earnings exceeded expectations with a 15% increase "
            "in revenue driven by strong demand for cloud AI services. Operating "
            "margins improved to 28%, and the company raised full-year guidance."
        )
        analysis_chunks: list[str] = []
        for part in analyzer.analyze(text):
            analysis_chunks.append(part)
        print(f"Analysis: {''.join(analysis_chunks)}")
        print()

        # --- Example 5b: Thread-safe parallel streaming ---
        print("=" * 60)
        print("Example 5b: Thread-safe parallel streaming")
        print("=" * 60)
        parallel_result = analyzer.analyze_parallel(text)
        print(f"Category: {parallel_result['category']}")
        print(f"Summary:  {parallel_result['summary']}")
        print(f"Chunks:   {len(parallel_result['summary_chunks'])}")
        print()

        # --- Example 6: Partial consumption (early break) ---
        print("=" * 60)
        print("Example 6: Partial consumption (early break)")
        print("=" * 60)
        consumed: list[str] = []
        for num in stream_numbers(100):
            consumed.append(num)
            if len(consumed) >= 5:
                break
        print(f"Consumed {len(consumed)} of 100: {consumed}")
        print("(Span has yield_count=5, generator_completed=False)")
        print()

        # --- Example 7: Async generator ---
        print("=" * 60)
        print("Example 7: Async generator")
        print("=" * 60)
        async_results = asyncio.run(run_async_example())
        print(f"Async items: {async_results}")
        print("(Span has yield_count=4, generator_completed=True)")
        print()

        # --- Example 8: Error mid-stream ---
        print("=" * 60)
        print("Example 8: Error mid-stream")
        print("=" * 60)
        partial: list[str] = []
        try:
            for text in stream_with_error(client, "Tell me a story.", fail_after=3):
                partial.append(text)
        except RuntimeError as e:
            print(f"Expected error: {e}")
            print(f"Partial output ({len(partial)} chunks): {''.join(partial)}")
            print("(Span has status=ERROR + exception event + partial output)")
        print()

    finally:
        client.close()
        shutdown()

    print("Done. Expected trace structure:")
    print("  stream-response          (root, type=llm, yield_count=N, output=joined string)")
    print("  stream-no-output         (root, type=llm, yield_count=N, no output attr)")
    print("  stream-raw-chunks        (root, type=llm, output=custom aggregated dict)")
    print("  word-stream              (root, type=tool, output='Thequickbrownfox...')")
    print("  stream-analyze           (root, type=chain)")
    print("    -> classify            (child, type=tool)")
    print("    -> stream-summarize    (child, type=llm, yield_count=N)")
    print("  stream-analyze-parallel  (root, type=chain)")
    print("    -> classify            (child, type=tool)         # thread 1")
    print("    -> stream-summarize    (child, type=llm)           # thread 2, consumed in-thread")
    print("  number-stream            (root, yield_count=5, generator_completed=False)")
    print("  async-data-stream        (root, type=tool, yield_count=4, generator_completed=True)")
    print("  error-mid-stream         (root, type=llm, status=ERROR, partial output)")


if __name__ == "__main__":
    if not API_KEY:
        print("Error: BUD_API_KEY environment variable is not set.")
        print("Usage: BUD_API_KEY=your-key python examples/observability/track_streaming.py")
        raise SystemExit(1)
    main()
