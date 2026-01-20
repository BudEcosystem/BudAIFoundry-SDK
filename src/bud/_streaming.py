"""Server-Sent Events (SSE) streaming utilities for inference API."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from contextlib import AbstractContextManager, suppress
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from pydantic import ValidationError

if TYPE_CHECKING:
    import httpx

    from bud.models.common import BudModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound="BudModel")


class SSEParser:
    """Stateful SSE parser with bounded memory protection.

    Parses Server-Sent Events according to the SSE specification,
    with protection against memory exhaustion attacks.
    """

    MAX_LINE_LENGTH = 1_000_000  # 1MB per line
    MAX_EVENTS = 100_000  # Maximum events before stopping

    def __init__(self) -> None:
        self._data_buffer: list[str] = []
        self._event_type: str | None = None
        self._event_count = 0

    def feed(self, line: str) -> dict[str, Any] | None:
        """Feed a line to the parser and return an event if complete.

        Args:
            line: A single line from the SSE stream (with newline stripped).

        Returns:
            Event dict with 'data' key when complete, None otherwise.

        Raises:
            ValueError: If line exceeds maximum length or too many events.
        """
        if len(line) > self.MAX_LINE_LENGTH:
            raise ValueError(f"SSE line exceeds maximum length of {self.MAX_LINE_LENGTH}")

        if self._event_count >= self.MAX_EVENTS:
            raise ValueError(f"SSE stream exceeded maximum of {self.MAX_EVENTS} events")

        # Empty line signals end of event
        if not line:
            if self._data_buffer:
                data = "\n".join(self._data_buffer)
                self._data_buffer = []
                self._event_count += 1
                return {"data": data, "event": self._event_type}
            return None

        # Parse field
        if line.startswith(":"):
            # Comment, ignore
            return None

        if ":" in line:
            field, _, value = line.partition(":")
            # Remove leading space from value per SSE spec
            if value.startswith(" "):
                value = value[1:]
        else:
            field = line
            value = ""

        if field == "data":
            self._data_buffer.append(value)
        elif field == "event":
            self._event_type = value
        # Ignore other fields (id, retry)

        return None


class Stream(Generic[T]):
    """Synchronous SSE stream with context manager support.

    Iterates over SSE events from an HTTP response and yields
    parsed model instances.

    The stream must be closed after use to release resources.
    Use as a context manager or call close() explicitly.

    Example:
        # As context manager (recommended)
        with stream as s:
            for chunk in s:
                print(chunk)

        # Or iterate directly (closes automatically after iteration)
        for chunk in stream:
            print(chunk)
    """

    def __init__(
        self,
        response: httpx.Response,
        model_cls: type[T],
        response_context: AbstractContextManager[httpx.Response] | None = None,
    ) -> None:
        self._response = response
        self._model_cls = model_cls
        self._parser = SSEParser()
        self._closed = False
        self._response_context = response_context

    def __iter__(self) -> Iterator[T]:
        """Iterate over parsed events from the stream."""
        try:
            for line in self._response.iter_lines():
                if self._closed:
                    break

                event = self._parser.feed(line)
                if event is None:
                    continue

                data = event["data"]

                # Handle [DONE] termination signal
                if data == "[DONE]":
                    break

                # Parse JSON and validate with model
                try:
                    parsed = json.loads(data)
                    yield self._model_cls.model_validate(parsed)
                except json.JSONDecodeError as e:
                    # Log the error but continue - the data may be a partial line
                    logger.warning("Failed to parse SSE data as JSON: %s (data: %r)", e, data[:100])
                    continue
                except ValidationError as e:
                    # Log validation errors - these indicate API response format changes
                    logger.warning("Failed to validate SSE data: %s", e)
                    continue

        finally:
            self.close()

    def close(self) -> None:
        """Close the stream and release resources."""
        if not self._closed:
            self._closed = True
            self._response.close()
            # Also exit the response context manager if we have one
            if self._response_context is not None:
                with suppress(Exception):
                    self._response_context.__exit__(None, None, None)

    def __enter__(self) -> Stream[T]:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
