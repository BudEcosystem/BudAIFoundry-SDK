"""Responses API streaming utilities.

Provides ResponseStream and AsyncResponseStream for iterating over
Server-Sent Events from the /v1/responses endpoint. Uses the openai
library's type system for event parsing.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Iterator
from contextlib import AbstractContextManager, suppress
from typing import TYPE_CHECKING, Any

from pydantic import TypeAdapter

from bud._streaming import SSEParser

if TYPE_CHECKING:
    import httpx

logger = logging.getLogger(__name__)

# Lazy-loaded TypeAdapter for the discriminated union of ~53 event types.
# Initialized on first use to avoid import-time dependency on openai.
_event_adapter: TypeAdapter[Any] | None = None


def _get_event_adapter() -> TypeAdapter[Any]:
    """Return (and cache) a TypeAdapter for ResponseStreamEvent."""
    global _event_adapter  # noqa: PLW0603
    if _event_adapter is None:
        from openai.types.responses import ResponseStreamEvent

        _event_adapter = TypeAdapter(ResponseStreamEvent)
    return _event_adapter


class ResponseStream:
    """Synchronous SSE stream for the Responses API.

    Iterates over SSE events from an HTTP response and yields parsed
    ResponseStreamEvent subtypes. Captures the ``response.completed``
    event's full Response object for post-stream access (e.g. usage data).

    Example:
        with stream as s:
            for event in s:
                if event.type == "response.output_text.delta":
                    print(event.delta, end="")
        # After iteration:
        print(stream.completed_response.usage)
    """

    def __init__(
        self,
        response: httpx.Response,
        response_context: AbstractContextManager[httpx.Response] | None = None,
    ) -> None:
        self._response = response
        self._parser = SSEParser()
        self._closed = False
        self._response_context = response_context
        self._completed_response: Any | None = None

    @property
    def completed_response(self) -> Any | None:
        """The full Response object from the ``response.completed`` SSE event.

        Available after the stream has been fully consumed. Returns None if
        the stream was closed early or the event was not received.
        """
        return self._completed_response

    def __iter__(self) -> Iterator[Any]:
        """Iterate over parsed ResponseStreamEvent objects."""
        adapter = _get_event_adapter()
        try:
            for line in self._response.iter_lines():
                if self._closed:
                    break

                event = self._parser.feed(line)
                if event is None:
                    continue

                data = event["data"]

                if data == "[DONE]":
                    break

                try:
                    parsed_json = json.loads(data)
                    parsed_event = adapter.validate_python(parsed_json)
                except json.JSONDecodeError as e:
                    logger.warning("Failed to parse SSE data as JSON: %s (data: %r)", e, data[:100])
                    continue
                except Exception as e:
                    logger.warning("Failed to validate SSE event: %s", e)
                    continue

                # Capture the completed response for post-stream access
                if getattr(parsed_event, "type", None) == "response.completed":
                    self._completed_response = getattr(parsed_event, "response", None)

                yield parsed_event

        finally:
            self.close()

    def close(self) -> None:
        """Close the stream and release resources."""
        if not self._closed:
            self._closed = True
            self._response.close()
            if self._response_context is not None:
                with suppress(Exception):
                    self._response_context.__exit__(None, None, None)

    def __enter__(self) -> ResponseStream:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class AsyncResponseStream:
    """Asynchronous SSE stream for the Responses API.

    Async version of ResponseStream. Uses ``response.aiter_lines()``
    for non-blocking iteration.

    Example:
        async with stream as s:
            async for event in s:
                if event.type == "response.output_text.delta":
                    print(event.delta, end="")
    """

    def __init__(
        self,
        response: httpx.Response,
        response_context: Any | None = None,
    ) -> None:
        self._response = response
        self._parser = SSEParser()
        self._closed = False
        self._response_context = response_context
        self._completed_response: Any | None = None

    @property
    def completed_response(self) -> Any | None:
        """The full Response object from the ``response.completed`` SSE event."""
        return self._completed_response

    async def __aiter__(self) -> AsyncIterator[Any]:
        """Iterate over parsed ResponseStreamEvent objects asynchronously."""
        adapter = _get_event_adapter()
        try:
            async for line in self._response.aiter_lines():
                if self._closed:
                    break

                event = self._parser.feed(line)
                if event is None:
                    continue

                data = event["data"]

                if data == "[DONE]":
                    break

                try:
                    parsed_json = json.loads(data)
                    parsed_event = adapter.validate_python(parsed_json)
                except json.JSONDecodeError as e:
                    logger.warning("Failed to parse SSE data as JSON: %s (data: %r)", e, data[:100])
                    continue
                except Exception as e:
                    logger.warning("Failed to validate SSE event: %s", e)
                    continue

                if getattr(parsed_event, "type", None) == "response.completed":
                    self._completed_response = getattr(parsed_event, "response", None)

                yield parsed_event

        finally:
            await self.aclose()

    async def aclose(self) -> None:
        """Close the stream and release resources."""
        if not self._closed:
            self._closed = True
            await self._response.aclose()
            if self._response_context is not None:
                with suppress(Exception):
                    if hasattr(self._response_context, "__aexit__"):
                        await self._response_context.__aexit__(None, None, None)
                    else:
                        self._response_context.__exit__(None, None, None)

    async def __aenter__(self) -> AsyncResponseStream:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()
