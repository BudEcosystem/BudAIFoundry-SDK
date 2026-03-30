"""A2A protocol SSE streaming utilities.

Provides A2AStream and AsyncA2AStream for iterating over Server-Sent Events
from A2A JSON-RPC streaming endpoints. Each SSE event contains a full
JSON-RPC 2.0 response envelope that must be unwrapped before model parsing.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Iterator
from contextlib import AbstractContextManager, suppress
from typing import TYPE_CHECKING, Any

from bud._jsonrpc import unwrap_sse_event
from bud._streaming import SSEParser
from bud.exceptions import A2AError
from bud.models.a2a import (
    A2AStreamEvent,
    Message,
    Task,
    TaskArtifactUpdateEvent,
    TaskStatusUpdateEvent,
)

if TYPE_CHECKING:
    import httpx

logger = logging.getLogger(__name__)


def _parse_stream_event(data: dict[str, Any], version: str) -> A2AStreamEvent:
    """Parse an unwrapped stream result into a typed event.

    Handles three formats:
    - v0.3 ``kind``-based: ``{"kind": "status-update", ...}``
    - v1.0 wrapper-based: ``{"statusUpdate": {...}}``
    - Direct (bud-gateway): ``{"artifact": {...}, "append": true, ...}``

    Args:
        data: The ``result`` dict from a JSON-RPC SSE event.
        version: A2A protocol version ("0.3" or "1.0").

    Returns:
        One of Task, Message, TaskStatusUpdateEvent, TaskArtifactUpdateEvent.
    """
    # --- v0.3: discriminate by "kind" field ---
    if version == "0.3":
        kind = data.get("kind")
        if kind == "status-update":
            return TaskStatusUpdateEvent.model_validate(data)
        if kind == "artifact-update":
            return TaskArtifactUpdateEvent.model_validate(data)
        if kind == "task" or ("id" in data and "status" in data):
            return Task.model_validate(data)
        if kind == "message" or ("role" in data and "parts" in data):
            return Message.model_validate(data)
    else:
        # --- v1.0: discriminate by wrapper key ---
        if "statusUpdate" in data:
            return TaskStatusUpdateEvent.model_validate(data["statusUpdate"])
        if "artifactUpdate" in data:
            return TaskArtifactUpdateEvent.model_validate(data["artifactUpdate"])
        if "task" in data and isinstance(data["task"], dict):
            return Task.model_validate(data["task"])
        if "message" in data and isinstance(data["message"], dict) and "parts" in data["message"]:
            return Message.model_validate(data["message"])

    # --- Fallback: field-based detection (handles direct format from bud-gateway) ---
    if "artifact" in data and isinstance(data["artifact"], dict):
        return TaskArtifactUpdateEvent.model_validate(data)
    if "status" in data and "id" not in data:
        return TaskStatusUpdateEvent.model_validate(data)
    if "id" in data and "status" in data:
        return Task.model_validate(data)
    if "role" in data and "parts" in data:
        return Message.model_validate(data)

    # Last resort
    return Task.model_validate(data)


class A2AStream:
    """Synchronous SSE stream for A2A streaming responses.

    Each SSE event contains a JSON-RPC 2.0 response envelope. The stream
    unwraps the envelope and yields typed event objects.

    Example:
        with stream as s:
            for event in s:
                if isinstance(event, TaskArtifactUpdateEvent):
                    print(event.artifact.parts[0].text, end="")
        print(stream.final_task)
    """

    def __init__(
        self,
        response: httpx.Response,
        response_context: AbstractContextManager[httpx.Response] | None = None,
        a2a_version: str = "1.0",
    ) -> None:
        self._response = response
        self._parser = SSEParser()
        self._closed = False
        self._response_context = response_context
        self._a2a_version = a2a_version
        self._final_task: Task | None = None

    @property
    def final_task(self) -> Task | None:
        """The last Task object seen in the stream. Available after iteration."""
        return self._final_task

    def __iter__(self) -> Iterator[A2AStreamEvent]:
        """Iterate over parsed A2A stream events."""
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
                    rpc_response = json.loads(data)
                    result = unwrap_sse_event(rpc_response)
                    parsed = _parse_stream_event(result, self._a2a_version)

                    if isinstance(parsed, Task):
                        self._final_task = parsed

                    yield parsed
                except json.JSONDecodeError as e:
                    logger.warning("A2A SSE: invalid JSON: %s (data: %r)", e, data[:100])
                    continue
                except A2AError:
                    raise
                except Exception as e:
                    logger.warning("A2A SSE: failed to parse event: %s", e)
                    continue

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

    def __enter__(self) -> A2AStream:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class AsyncA2AStream:
    """Asynchronous SSE stream for A2A streaming responses.

    Async version of A2AStream. Uses ``response.aiter_lines()``
    for non-blocking iteration.

    Example:
        async with stream as s:
            async for event in s:
                if isinstance(event, TaskArtifactUpdateEvent):
                    print(event.artifact.parts[0].text, end="")
    """

    def __init__(
        self,
        response: httpx.Response,
        response_context: Any | None = None,
        a2a_version: str = "1.0",
    ) -> None:
        self._response = response
        self._parser = SSEParser()
        self._closed = False
        self._response_context = response_context
        self._a2a_version = a2a_version
        self._final_task: Task | None = None

    @property
    def final_task(self) -> Task | None:
        """The last Task object seen in the stream. Available after iteration."""
        return self._final_task

    async def __aiter__(self) -> AsyncIterator[A2AStreamEvent]:
        """Iterate over parsed A2A stream events asynchronously."""
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
                    rpc_response = json.loads(data)
                    result = unwrap_sse_event(rpc_response)
                    parsed = _parse_stream_event(result, self._a2a_version)

                    if isinstance(parsed, Task):
                        self._final_task = parsed

                    yield parsed
                except json.JSONDecodeError as e:
                    logger.warning("A2A SSE: invalid JSON: %s (data: %r)", e, data[:100])
                    continue
                except A2AError:
                    raise
                except Exception as e:
                    logger.warning("A2A SSE: failed to parse event: %s", e)
                    continue

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

    async def __aenter__(self) -> AsyncA2AStream:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()
