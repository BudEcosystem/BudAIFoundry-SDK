"""Span wrapper for streaming inference responses.

Manages span lifecycle across SSE streaming: records TTFT on first chunk,
total chunks on completion, and properly ends span + detaches context in finally.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Iterator
from typing import Any, Generic, TypeVar

from opentelemetry import context
from opentelemetry.trace import StatusCode

T = TypeVar("T")


class TracedStream(Generic[T]):
    """Wraps a sync/async iterator to track span across SSE streaming."""

    def __init__(self, inner: Any, span: Any, context_token: Any) -> None:
        self._inner = inner
        self._span = span
        self._context_token = context_token
        self._chunk_count = 0
        self._first_chunk_time: float | None = None
        self._start_time = time.monotonic()

    def __iter__(self) -> Iterator[T]:
        try:
            for chunk in self._inner:
                if self._first_chunk_time is None:
                    self._first_chunk_time = time.monotonic()
                    ttft_ms = (self._first_chunk_time - self._start_time) * 1000
                    self._span.set_attribute("bud.inference.ttft_ms", ttft_ms)
                self._chunk_count += 1
                yield chunk
        except Exception as exc:
            self._span.set_status(StatusCode.ERROR, str(exc))
            raise
        finally:
            self._span.set_attribute("bud.inference.chunks", self._chunk_count)
            self._span.end()
            if self._context_token is not None:
                context.detach(self._context_token)

    async def __aiter__(self) -> AsyncIterator[T]:
        try:
            async for chunk in self._inner:
                if self._first_chunk_time is None:
                    self._first_chunk_time = time.monotonic()
                    ttft_ms = (self._first_chunk_time - self._start_time) * 1000
                    self._span.set_attribute("bud.inference.ttft_ms", ttft_ms)
                self._chunk_count += 1
                yield chunk
        except Exception as exc:
            self._span.set_status(StatusCode.ERROR, str(exc))
            raise
        finally:
            self._span.set_attribute("bud.inference.chunks", self._chunk_count)
            self._span.end()
            if self._context_token is not None:
                context.detach(self._context_token)
