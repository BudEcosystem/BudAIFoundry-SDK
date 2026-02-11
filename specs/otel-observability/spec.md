# Technical Specification: v1/responses Endpoint + `track_responses()`

This spec contains exact code snippets for every file to modify or create. Code is grounded in the actual codebase patterns read from source.

---

## 1. `pyproject.toml` — Add openai dependency

**File:** `pyproject.toml` (line 36-44)

**Change:** Add `"openai>=1.90.0"` to the `dependencies` array.

```python
# BEFORE (line 36-44):
dependencies = [
    "httpx>=0.27.0",
    "pydantic>=2.0.0",
    "typer>=0.12.0",
    "rich>=13.0.0",
    "anyio>=4.0.0",
    "tomli>=2.0.0;python_version<'3.11'",
    "tomli-w>=1.0.0",
]

# AFTER:
dependencies = [
    "httpx>=0.27.0",
    "pydantic>=2.0.0",
    "typer>=0.12.0",
    "rich>=13.0.0",
    "anyio>=4.0.0",
    "tomli>=2.0.0;python_version<'3.11'",
    "tomli-w>=1.0.0",
    "openai>=1.90.0",
]
```

---

## 2. `src/bud/_http.py` — Add `async_stream()` to `AsyncHttpClient`

**File:** `src/bud/_http.py`

**Change:** Add imports at top and `async_stream()` method after line 364 (after `async def delete`).

### 2a. Add import at top (line 11-17)

```python
# BEFORE (line 11-17):
import contextlib
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, TypeVar

# AFTER:
import contextlib
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import TYPE_CHECKING, Any, TypeVar
```

### 2b. Add `async_stream()` method (after line 364, after `async def delete`)

```python
    @asynccontextmanager
    async def async_stream(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> AsyncIterator[httpx.Response]:
        """Stream HTTP response for SSE endpoints (async).

        Args:
            method: HTTP method (typically POST).
            path: API path.
            json: Request body as JSON.

        Yields:
            httpx.Response object for async streaming iteration.
        """
        stream_timeout = httpx.Timeout(
            connect=10.0,
            read=600.0,
            write=30.0,
            pool=5.0,
        )

        outgoing_headers: dict[str, str] = {
            "Accept": "text/event-stream",
        }
        _inject_trace_context(outgoing_headers)

        async with self._client.stream(
            method,
            path,
            json=json,
            headers=outgoing_headers,
            timeout=stream_timeout,
        ) as response:
            if not response.is_success:
                await response.aread()
                self._handle_response(response)
            yield response
```

---

## 3. `src/bud/_response_streaming.py` — NEW FILE

**File:** `src/bud/_response_streaming.py` (create new)

```python
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
                    logger.warning(
                        "Failed to parse SSE data as JSON: %s (data: %r)", e, data[:100]
                    )
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
                    logger.warning(
                        "Failed to parse SSE data as JSON: %s (data: %r)", e, data[:100]
                    )
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
```

---

## 4. `src/bud/resources/inference.py` — Add `Responses` + `AsyncResponses`

**File:** `src/bud/resources/inference.py`

**Change:** Add imports at top and two new classes at end of file.

### 4a. Update imports (line 1-19)

```python
# BEFORE (line 1-19):
"""OpenAI-compatible inference API resources."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, overload

from bud._streaming import Stream
from bud.models.inference import (
    ChatCompletion,
    ChatCompletionChunk,
    ClassifyResponse,
    EmbeddingResponse,
    Model,
    ModelList,
)
from bud.resources._base import SyncResource

if TYPE_CHECKING:
    from bud._http import HttpClient

# AFTER:
"""OpenAI-compatible inference API resources."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, overload

from bud._streaming import Stream
from bud.models.inference import (
    ChatCompletion,
    ChatCompletionChunk,
    ClassifyResponse,
    EmbeddingResponse,
    Model,
    ModelList,
)
from bud.resources._base import AsyncResource, SyncResource

if TYPE_CHECKING:
    from bud._http import AsyncHttpClient, HttpClient
    from bud._response_streaming import AsyncResponseStream, ResponseStream
```

### 4b. Append new classes at end of file (after line 333)

```python
class Responses(SyncResource):
    """OpenAI Responses API operations.

    Create responses using the /v1/responses endpoint with support for
    multi-turn conversations, tool use, and streaming.
    """

    @overload
    def create(
        self,
        *,
        model: str | None = None,
        input: str | list[dict[str, Any]] | None = None,
        stream: Literal[False] = False,
        instructions: str | None = None,
        previous_response_id: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        max_output_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        parallel_tool_calls: bool | None = None,
        reasoning: dict[str, Any] | None = None,
        metadata: dict[str, str] | None = None,
        user: str | None = None,
        prompt: dict[str, Any] | None = None,
        store: bool | None = None,
        background: bool | None = None,
        service_tier: str | None = None,
        text: dict[str, Any] | None = None,
        truncation: str | None = None,
        include: list[str] | None = None,
    ) -> Any: ...  # openai.types.responses.Response

    @overload
    def create(
        self,
        *,
        model: str | None = None,
        input: str | list[dict[str, Any]] | None = None,
        stream: Literal[True],
        instructions: str | None = None,
        previous_response_id: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        max_output_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        parallel_tool_calls: bool | None = None,
        reasoning: dict[str, Any] | None = None,
        metadata: dict[str, str] | None = None,
        user: str | None = None,
        prompt: dict[str, Any] | None = None,
        store: bool | None = None,
        background: bool | None = None,
        service_tier: str | None = None,
        text: dict[str, Any] | None = None,
        truncation: str | None = None,
        include: list[str] | None = None,
    ) -> ResponseStream: ...

    def create(
        self,
        *,
        model: str | None = None,
        input: str | list[dict[str, Any]] | None = None,
        stream: bool = False,
        instructions: str | None = None,
        previous_response_id: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        max_output_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        parallel_tool_calls: bool | None = None,
        reasoning: dict[str, Any] | None = None,
        metadata: dict[str, str] | None = None,
        user: str | None = None,
        prompt: dict[str, Any] | None = None,
        store: bool | None = None,
        background: bool | None = None,
        service_tier: str | None = None,
        text: dict[str, Any] | None = None,
        truncation: str | None = None,
        include: list[str] | None = None,
    ) -> Any:
        """Create a response using the Responses API.

        Args:
            model: Model ID. Required unless ``prompt`` is provided.
            input: Text string or list of input messages.
            stream: If True, returns a ResponseStream.
            instructions: System instructions for the model.
            previous_response_id: ID of a previous response for multi-turn.
            temperature: Sampling temperature (0-2).
            top_p: Nucleus sampling probability.
            max_output_tokens: Maximum tokens to generate.
            tools: List of tools the model may call.
            tool_choice: Controls which tool is called.
            parallel_tool_calls: Allow parallel tool calls.
            reasoning: Reasoning configuration.
            metadata: Key-value metadata.
            user: Unique user identifier.
            prompt: Stored prompt configuration (alternative to model+input).
            store: Whether to store the response.
            background: Whether to run in the background.
            service_tier: Service tier for the request.
            text: Text generation configuration.
            truncation: Truncation strategy.
            include: Additional fields to include in response.

        Returns:
            openai.types.responses.Response or ResponseStream if streaming.

        Raises:
            ValueError: If neither ``model`` nor ``prompt`` is provided.

        Example:
            # Non-streaming
            response = client.responses.create(
                model="gpt-4.1",
                input="What is the capital of France?",
            )
            print(response.output_text)

            # Streaming
            stream = client.responses.create(
                model="gpt-4.1",
                input="Tell me a story",
                stream=True,
            )
            for event in stream:
                if event.type == "response.output_text.delta":
                    print(event.delta, end="")
        """
        if model is None and prompt is None:
            raise ValueError("At least one of 'model' or 'prompt' must be provided")

        payload: dict[str, Any] = {}
        if stream:
            payload["stream"] = True

        # Add all non-None parameters
        optional_params = {
            "model": model,
            "input": input,
            "instructions": instructions,
            "previous_response_id": previous_response_id,
            "temperature": temperature,
            "top_p": top_p,
            "max_output_tokens": max_output_tokens,
            "tools": tools,
            "tool_choice": tool_choice,
            "parallel_tool_calls": parallel_tool_calls,
            "reasoning": reasoning,
            "metadata": metadata,
            "user": user,
            "prompt": prompt,
            "store": store,
            "background": background,
            "service_tier": service_tier,
            "text": text,
            "truncation": truncation,
            "include": include,
        }
        payload.update({k: v for k, v in optional_params.items() if v is not None})

        if stream:
            from bud._response_streaming import ResponseStream

            response_ctx = self._http.stream("POST", "/v1/responses", json=payload)
            response = response_ctx.__enter__()
            return ResponseStream(response, response_context=response_ctx)
        else:
            from openai.types.responses import Response

            data = self._http.post("/v1/responses", json=payload)
            return Response.model_validate(data)


class AsyncResponses(AsyncResource):
    """Async OpenAI Responses API operations.

    Async version of Responses resource.
    """

    @overload
    async def create(
        self,
        *,
        model: str | None = None,
        input: str | list[dict[str, Any]] | None = None,
        stream: Literal[False] = False,
        instructions: str | None = None,
        previous_response_id: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        max_output_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        parallel_tool_calls: bool | None = None,
        reasoning: dict[str, Any] | None = None,
        metadata: dict[str, str] | None = None,
        user: str | None = None,
        prompt: dict[str, Any] | None = None,
        store: bool | None = None,
        background: bool | None = None,
        service_tier: str | None = None,
        text: dict[str, Any] | None = None,
        truncation: str | None = None,
        include: list[str] | None = None,
    ) -> Any: ...  # openai.types.responses.Response

    @overload
    async def create(
        self,
        *,
        model: str | None = None,
        input: str | list[dict[str, Any]] | None = None,
        stream: Literal[True],
        instructions: str | None = None,
        previous_response_id: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        max_output_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        parallel_tool_calls: bool | None = None,
        reasoning: dict[str, Any] | None = None,
        metadata: dict[str, str] | None = None,
        user: str | None = None,
        prompt: dict[str, Any] | None = None,
        store: bool | None = None,
        background: bool | None = None,
        service_tier: str | None = None,
        text: dict[str, Any] | None = None,
        truncation: str | None = None,
        include: list[str] | None = None,
    ) -> AsyncResponseStream: ...

    async def create(
        self,
        *,
        model: str | None = None,
        input: str | list[dict[str, Any]] | None = None,
        stream: bool = False,
        instructions: str | None = None,
        previous_response_id: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        max_output_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        parallel_tool_calls: bool | None = None,
        reasoning: dict[str, Any] | None = None,
        metadata: dict[str, str] | None = None,
        user: str | None = None,
        prompt: dict[str, Any] | None = None,
        store: bool | None = None,
        background: bool | None = None,
        service_tier: str | None = None,
        text: dict[str, Any] | None = None,
        truncation: str | None = None,
        include: list[str] | None = None,
    ) -> Any:
        """Create a response using the Responses API (async).

        Same parameters as Responses.create(). See that method for full docs.
        """
        if model is None and prompt is None:
            raise ValueError("At least one of 'model' or 'prompt' must be provided")

        payload: dict[str, Any] = {}
        if stream:
            payload["stream"] = True

        optional_params = {
            "model": model,
            "input": input,
            "instructions": instructions,
            "previous_response_id": previous_response_id,
            "temperature": temperature,
            "top_p": top_p,
            "max_output_tokens": max_output_tokens,
            "tools": tools,
            "tool_choice": tool_choice,
            "parallel_tool_calls": parallel_tool_calls,
            "reasoning": reasoning,
            "metadata": metadata,
            "user": user,
            "prompt": prompt,
            "store": store,
            "background": background,
            "service_tier": service_tier,
            "text": text,
            "truncation": truncation,
            "include": include,
        }
        payload.update({k: v for k, v in optional_params.items() if v is not None})

        if stream:
            from bud._response_streaming import AsyncResponseStream

            response_ctx = self._http.async_stream("POST", "/v1/responses", json=payload)
            response = await response_ctx.__aenter__()
            return AsyncResponseStream(response, response_context=response_ctx)
        else:
            from openai.types.responses import Response

            data = await self._http.post("/v1/responses", json=payload)
            return Response.model_validate(data)
```

---

## 5. `src/bud/resources/__init__.py` — Export new classes

**File:** `src/bud/resources/__init__.py`

**Full replacement:**

```python
"""API resource modules."""

from bud.resources.actions import Actions, AsyncActions
from bud.resources.audit import AsyncAudit, Audit
from bud.resources.auth import AsyncAuth, Auth
from bud.resources.benchmarks import AsyncBenchmarks, Benchmarks
from bud.resources.clusters import AsyncClusters, Clusters
from bud.resources.events import AsyncEvents, Events
from bud.resources.executions import AsyncExecutions, Executions
from bud.resources.inference import (
    AsyncResponses,
    Chat,
    ChatCompletions,
    Classifications,
    Embeddings,
    InferenceModels,
    Responses,
)
from bud.resources.pipelines import AsyncPipelines, Pipelines
from bud.resources.schedules import AsyncSchedules, Schedules
from bud.resources.webhooks import AsyncWebhooks, Webhooks

__all__ = [
    # Core resources
    "Pipelines",
    "AsyncPipelines",
    "Executions",
    "AsyncExecutions",
    "Schedules",
    "AsyncSchedules",
    "Webhooks",
    "AsyncWebhooks",
    "Events",
    "AsyncEvents",
    "Actions",
    "AsyncActions",
    # Additional resources
    "Auth",
    "AsyncAuth",
    "Audit",
    "AsyncAudit",
    "Benchmarks",
    "AsyncBenchmarks",
    "Clusters",
    "AsyncClusters",
    # Inference resources
    "Chat",
    "ChatCompletions",
    "Classifications",
    "Embeddings",
    "InferenceModels",
    "Responses",
    "AsyncResponses",
]
```

---

## 6. `src/bud/client.py` — Wire `client.responses`

**File:** `src/bud/client.py`

### 6a. Update import (line 22)

```python
# BEFORE (line 22):
from bud.resources.inference import Chat, Classifications, Embeddings, InferenceModels

# AFTER:
from bud.resources.inference import (
    AsyncResponses,
    Chat,
    Classifications,
    Embeddings,
    InferenceModels,
    Responses,
)
```

### 6b. Add `self.responses` to `BudClient.__init__` (after line 163)

```python
        # OpenAI-compatible inference resources
        self.chat = Chat(self._http)
        self.embeddings = Embeddings(self._http)
        self.classifications = Classifications(self._http)
        self.models = InferenceModels(self._http)
        self.responses = Responses(self._http)  # <-- ADD THIS LINE
```

### 6c. Add `self.responses` to `AsyncBudClient.__init__` (after line 371)

```python
        # Initialize resource managers
        self.auth = AsyncAuth(self._http)
        self.pipelines = AsyncPipelines(self._http)
        self.executions = AsyncExecutions(self._http)
        self.schedules = AsyncSchedules(self._http)
        self.webhooks = AsyncWebhooks(self._http)
        self.events = AsyncEvents(self._http)
        self.actions = AsyncActions(self._http)
        self.benchmarks = AsyncBenchmarks(self._http)
        self.clusters = AsyncClusters(self._http)
        self.audit = AsyncAudit(self._http)
        self.responses = AsyncResponses(self._http)  # <-- ADD THIS LINE
```

---

## 7. `src/bud/observability/_genai_attributes.py` — Add constants

**File:** `src/bud/observability/_genai_attributes.py`

**Change:** Append the following block at end of file (after line 123).

```python
# ---------------------------------------------------------------------------
# Responses API attributes
# ---------------------------------------------------------------------------

GENAI_OPERATION_NAME = "gen_ai.operation.name"
GENAI_CONVERSATION_ID = "gen_ai.conversation.id"
GENAI_RESPONSE_STATUS = "gen_ai.response.status"
BUD_INFERENCE_RESPONSE_OUTPUT_TEXT = "bud.inference.response.output_text"
BUD_RESPONSES_REQUEST_INPUT = "bud.inference.request.input"
BUD_RESPONSES_REQUEST_INSTRUCTIONS = "bud.inference.request.instructions"
BUD_RESPONSES_REQUEST_PROMPT = "bud.inference.request.prompt"

# ---------------------------------------------------------------------------
# Mapping: Responses create() kwarg name -> OTel attribute key
# ---------------------------------------------------------------------------

RESPONSES_INPUT_ATTR_MAP: dict[str, str] = {
    "model": GENAI_REQUEST_MODEL,
    "temperature": GENAI_REQUEST_TEMPERATURE,
    "top_p": GENAI_REQUEST_TOP_P,
    "max_output_tokens": GENAI_REQUEST_MAX_TOKENS,
    "stream": BUD_INFERENCE_STREAM,
    "input": BUD_RESPONSES_REQUEST_INPUT,
    "instructions": BUD_RESPONSES_REQUEST_INSTRUCTIONS,
    "tools": BUD_INFERENCE_REQUEST_TOOLS,
    "tool_choice": BUD_INFERENCE_REQUEST_TOOL_CHOICE,
    "user": BUD_INFERENCE_REQUEST_USER,
    "prompt": BUD_RESPONSES_REQUEST_PROMPT,
    "previous_response_id": GENAI_CONVERSATION_ID,
}

# ---------------------------------------------------------------------------
# Responses API default field sets
# ---------------------------------------------------------------------------

RESPONSES_DEFAULT_INPUT_FIELDS: frozenset[str] = frozenset(
    {
        "model",
        "temperature",
        "top_p",
        "max_output_tokens",
        "stream",
        "tool_choice",
        "input",
        "instructions",
        "tools",
        "user",
        "prompt",
        "previous_response_id",
        "reasoning",
        "store",
        "service_tier",
        "truncation",
        "include",
    }
)

RESPONSES_DEFAULT_OUTPUT_FIELDS: frozenset[str] = frozenset(
    {
        "id",
        "status",
        "created_at",
        "model",
        "usage",
        "output_text",
    }
)

# Backward compatibility aliases
RESPONSES_SAFE_INPUT_FIELDS = RESPONSES_DEFAULT_INPUT_FIELDS
RESPONSES_SAFE_OUTPUT_FIELDS = RESPONSES_DEFAULT_OUTPUT_FIELDS
```

---

## 8. `src/bud/observability/_responses_tracker.py` — NEW FILE

**File:** `src/bud/observability/_responses_tracker.py` (create new)

```python
"""Inference-level tracing for the Responses API.

Instruments ``client.responses.create()`` with OTel spans for both
streaming and non-streaming calls. Records request parameters, response
metadata, token usage, and time-to-first-token as span attributes following
the OpenTelemetry GenAI Semantic Conventions.

Usage::

    from bud import BudClient
    from bud.observability import track_responses

    client = BudClient(api_key="...")
    track_responses(client)

    response = client.responses.create(model="gpt-4.1", input="Hello!")
"""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any

from bud.observability._genai_attributes import (
    BUD_INFERENCE_CHUNKS,
    BUD_INFERENCE_OPERATION,
    BUD_INFERENCE_RESPONSE_OUTPUT_TEXT,
    BUD_INFERENCE_STREAM,
    BUD_INFERENCE_STREAM_COMPLETED,
    BUD_INFERENCE_TTFT_MS,
    GENAI_CONVERSATION_ID,
    GENAI_OPERATION_NAME,
    GENAI_RESPONSE_CREATED,
    GENAI_RESPONSE_ID,
    GENAI_RESPONSE_MODEL,
    GENAI_RESPONSE_STATUS,
    GENAI_SYSTEM,
    GENAI_USAGE_INPUT_TOKENS,
    GENAI_USAGE_OUTPUT_TOKENS,
    GENAI_USAGE_TOTAL_TOKENS,
    RESPONSES_INPUT_ATTR_MAP,
    RESPONSES_SAFE_INPUT_FIELDS,
    RESPONSES_SAFE_OUTPUT_FIELDS,
)
from bud.observability._track import _is_noop, _record_exception, _set_ok_status

if TYPE_CHECKING:
    from bud.client import BudClient

logger = logging.getLogger("bud.observability")

# ---------------------------------------------------------------------------
# Type alias
# ---------------------------------------------------------------------------

FieldCapture = bool | list[str]

# ---------------------------------------------------------------------------
# Field resolution
# ---------------------------------------------------------------------------


def _resolve_fields(
    capture: FieldCapture,
    safe_defaults: frozenset[str],
) -> frozenset[str] | None:
    """Convert user-facing capture config into an internal field set.

    - ``True``  -> returns *safe_defaults*
    - ``False`` -> returns ``None`` (nothing captured)
    - ``list[str]`` -> returns ``frozenset(list)``
    """
    if capture is True:
        return safe_defaults
    if capture is False:
        return None
    return frozenset(capture)


# ---------------------------------------------------------------------------
# Request attribute extraction
# ---------------------------------------------------------------------------


def _extract_responses_request_attrs(
    kwargs: dict[str, Any],
    fields: frozenset[str] | None,
) -> dict[str, Any]:
    """Extract span attributes from ``create()`` keyword arguments.

    Only kwargs whose name appears in *fields* are captured.
    Returns empty dict when *fields* is ``None``.
    """
    if fields is None:
        return {}

    attrs: dict[str, Any] = {}
    for name in fields & kwargs.keys():
        value = kwargs[name]
        attr_key = RESPONSES_INPUT_ATTR_MAP.get(name)

        if name in ("input", "tools", "reasoning", "prompt"):
            target_key = attr_key or f"bud.inference.request.{name}"
            attrs[target_key] = json.dumps(value) if not isinstance(value, str) else value
        elif name == "tool_choice":
            target_key = attr_key or f"bud.inference.request.{name}"
            attrs[target_key] = json.dumps(value) if not isinstance(value, str) else value
        elif name == "include" and isinstance(value, list):
            target_key = attr_key or f"bud.inference.request.{name}"
            attrs[target_key] = json.dumps(value)
        else:
            target_key = attr_key or f"bud.inference.request.{name}"
            attrs[target_key] = value

    return attrs


# ---------------------------------------------------------------------------
# Response attribute extraction
# ---------------------------------------------------------------------------


def _extract_responses_response_attrs(
    response: Any,
    fields: frozenset[str] | None,
) -> dict[str, Any]:
    """Extract span attributes from an ``openai.types.responses.Response``.

    Returns empty dict when *fields* is ``None``.
    """
    if fields is None:
        return {}

    attrs: dict[str, Any] = {}

    if "id" in fields and hasattr(response, "id"):
        attrs[GENAI_RESPONSE_ID] = response.id

    if "model" in fields and hasattr(response, "model"):
        attrs[GENAI_RESPONSE_MODEL] = response.model

    if "status" in fields and hasattr(response, "status"):
        attrs[GENAI_RESPONSE_STATUS] = response.status

    if "created_at" in fields and hasattr(response, "created_at"):
        created = response.created_at
        if created is not None:
            # Convert datetime to float timestamp if needed
            if hasattr(created, "timestamp"):
                attrs[GENAI_RESPONSE_CREATED] = created.timestamp()
            else:
                attrs[GENAI_RESPONSE_CREATED] = float(created)

    if "usage" in fields:
        usage = getattr(response, "usage", None)
        if usage is not None:
            attrs[GENAI_USAGE_INPUT_TOKENS] = getattr(usage, "input_tokens", 0)
            attrs[GENAI_USAGE_OUTPUT_TOKENS] = getattr(usage, "output_tokens", 0)
            attrs[GENAI_USAGE_TOTAL_TOKENS] = getattr(usage, "total_tokens", 0)

    if "output_text" in fields:
        output_text = getattr(response, "output_text", None)
        if output_text is not None:
            attrs[BUD_INFERENCE_RESPONSE_OUTPUT_TEXT] = output_text

    return attrs


# ---------------------------------------------------------------------------
# TracedResponseStream
# ---------------------------------------------------------------------------


class TracedResponseStream:
    """Streaming wrapper that manages span lifecycle across iteration.

    Unlike TracedChatStream, this does not need chunk-by-chunk aggregation.
    The ``response.completed`` SSE event contains the full Response object
    with usage data, which the inner ResponseStream captures automatically.
    """

    def __init__(
        self,
        inner: Any,
        span: Any,
        context_token: Any,
        output_fields: frozenset[str] | None,
    ) -> None:
        self._inner = inner
        self._span = span
        self._context_token = context_token
        self._output_fields = output_fields
        self._chunk_count = 0
        self._completed = False
        self._finalized = False
        self._start_time = time.monotonic()
        self._first_chunk_time: float | None = None

    def __iter__(self):
        try:
            for event in self._inner:
                if self._first_chunk_time is None:
                    self._first_chunk_time = time.monotonic()
                    self._span.set_attribute(
                        BUD_INFERENCE_TTFT_MS,
                        (self._first_chunk_time - self._start_time) * 1000,
                    )
                self._chunk_count += 1
                yield event
            self._completed = True
        except GeneratorExit:
            pass
        except Exception as exc:
            _record_exception(self._span, exc)
            raise
        finally:
            self._finalize()

    def _finalize(self) -> None:
        if self._finalized:
            return
        self._finalized = True

        self._span.set_attribute(BUD_INFERENCE_CHUNKS, self._chunk_count)
        self._span.set_attribute(BUD_INFERENCE_STREAM_COMPLETED, self._completed)

        # Extract response attributes from the completed Response object
        completed_response = getattr(self._inner, "completed_response", None)
        if completed_response is not None:
            try:
                for k, v in _extract_responses_response_attrs(
                    completed_response, self._output_fields
                ).items():
                    self._span.set_attribute(k, v)
            except Exception:
                logger.debug("Failed to extract response attributes from stream", exc_info=True)

        if self._completed:
            _set_ok_status(self._span)

        self._span.end()
        if self._context_token is not None:
            try:
                from opentelemetry import context

                context.detach(self._context_token)
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def close(self) -> None:
        if hasattr(self._inner, "close"):
            self._inner.close()

    def __del__(self) -> None:
        if not self._finalized:
            logger.warning("TracedResponseStream was garbage-collected without iteration")
            self._finalize()


# ---------------------------------------------------------------------------
# Public API: track_responses()
# ---------------------------------------------------------------------------


def track_responses(
    client: BudClient,
    *,
    capture_input: FieldCapture = True,
    capture_output: FieldCapture = True,
    span_name: str = "responses",
) -> BudClient:
    """Instrument ``client.responses.create()`` with OTel spans.

    Args:
        client: The ``BudClient`` instance to instrument.
        capture_input: Controls which request kwargs are recorded.
            ``True`` = all fields, ``False`` = nothing,
            ``list[str]`` = exactly those fields.
        capture_output: Controls which response fields are recorded.
            ``True`` = all fields, ``False`` = nothing,
            ``list[str]`` = exactly those fields.
        span_name: Base span name. Streaming calls use ``"{span_name}.stream"``.

    Returns:
        The same *client* object (mutated in place).
    """
    # Step 1: Idempotency guard
    if getattr(client.responses, "_bud_tracked", False):
        return client

    # Step 2: Save original method reference
    original_create = client.responses.create

    # Step 3: Resolve field sets (once at patch time)
    input_fields = _resolve_fields(capture_input, RESPONSES_SAFE_INPUT_FIELDS)
    output_fields = _resolve_fields(capture_output, RESPONSES_SAFE_OUTPUT_FIELDS)

    # Step 4: Define wrapper
    def traced_create(**kwargs: Any) -> Any:
        if _is_noop():
            return original_create(**kwargs)

        from bud.observability import create_traced_span, get_tracer

        is_streaming = kwargs.get("stream", False)
        effective_span_name = f"{span_name}.stream" if is_streaming else span_name

        span, token = create_traced_span(effective_span_name, get_tracer("bud.inference"))

        # Always-on attributes
        span.set_attribute(GENAI_SYSTEM, "bud")
        span.set_attribute(BUD_INFERENCE_OPERATION, "responses")
        span.set_attribute(GENAI_OPERATION_NAME, "responses")
        span.set_attribute(BUD_INFERENCE_STREAM, bool(is_streaming))

        # Map previous_response_id to conversation.id
        prev_id = kwargs.get("previous_response_id")
        if prev_id is not None:
            span.set_attribute(GENAI_CONVERSATION_ID, prev_id)

        # Request attributes
        try:
            for k, v in _extract_responses_request_attrs(kwargs, input_fields).items():
                span.set_attribute(k, v)
        except Exception:
            logger.debug("Failed to extract request attributes", exc_info=True)

        # Call original
        try:
            result = original_create(**kwargs)
        except Exception as exc:
            _record_exception(span, exc)
            span.end()
            try:
                from opentelemetry import context

                context.detach(token)
            except Exception:
                pass
            raise

        # Handle response
        if is_streaming:
            return TracedResponseStream(result, span, token, output_fields)

        # Non-streaming: extract response attrs, finalize span
        try:
            for k, v in _extract_responses_response_attrs(result, output_fields).items():
                span.set_attribute(k, v)
        except Exception:
            logger.debug("Failed to extract response attributes", exc_info=True)

        _set_ok_status(span)
        span.end()
        try:
            from opentelemetry import context

            context.detach(token)
        except Exception:
            pass
        return result

    # Step 5: Monkey-patch
    client.responses.create = traced_create  # type: ignore[assignment]
    client.responses._bud_tracked = True  # type: ignore[attr-defined]
    return client
```

---

## 9. `src/bud/observability/__init__.py` — Register `track_responses`

**File:** `src/bud/observability/__init__.py`

### 9a. Update module docstring (line 1-13)

```python
# BEFORE (line 1-13):
"""bud.observability — Unified OTel-native observability for the BudAIFoundry SDK.

Public API:
    configure()          — Main entry point (3-5 lines to set up)
    shutdown()           — Flush and release resources
    is_configured()      — Check if observability is active
    get_tracer()         — Get OTel Tracer (or no-op)
    get_meter()          — Get OTel Meter (or no-op)
    extract_context()    — Extract W3C trace context from headers
    inject_context()     — Inject trace context into headers
    extract_from_request() — Extract context from Request objects
    track_chat_completions() — Instrument client.chat.completions.create()
"""

# AFTER:
"""bud.observability — Unified OTel-native observability for the BudAIFoundry SDK.

Public API:
    configure()          — Main entry point (3-5 lines to set up)
    shutdown()           — Flush and release resources
    is_configured()      — Check if observability is active
    get_tracer()         — Get OTel Tracer (or no-op)
    get_meter()          — Get OTel Meter (or no-op)
    extract_context()    — Extract W3C trace context from headers
    inject_context()     — Inject trace context into headers
    extract_from_request() — Extract context from Request objects
    track_chat_completions() — Instrument client.chat.completions.create()
    track_responses()    — Instrument client.responses.create()
"""
```

### 9b. Add lazy loader entry (line 219-230)

```python
# BEFORE (line 219-230):
def __getattr__(name: str) -> Any:
    if name == "TracedStream":
        return _lazy_traced_stream()
    if name == "track":
        from bud.observability._track import track

        return track
    if name == "track_chat_completions":
        from bud.observability._inference_tracker import track_chat_completions

        return track_chat_completions
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

# AFTER:
def __getattr__(name: str) -> Any:
    if name == "TracedStream":
        return _lazy_traced_stream()
    if name == "track":
        from bud.observability._track import track

        return track
    if name == "track_chat_completions":
        from bud.observability._inference_tracker import track_chat_completions

        return track_chat_completions
    if name == "track_responses":
        from bud.observability._responses_tracker import track_responses

        return track_responses
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

### 9c. Add to `__all__` (line 233-252)

```python
# Add "track_responses" to __all__ list:
__all__ = [
    "configure",
    "shutdown",
    "is_configured",
    "get_tracer",
    "get_meter",
    "extract_context",
    "inject_context",
    "extract_from_request",
    "create_traced_span",
    "get_current_span",
    "instrument_fastapi",
    "instrument_httpx",
    "ObservabilityConfig",
    "ObservabilityMode",
    "BaggageSpanProcessor",
    "TracedStream",
    "track",
    "track_chat_completions",
    "track_responses",
]
```

---

## 10. `tests/unit/test_responses.py` — NEW FILE

**File:** `tests/unit/test_responses.py` (create new)

```python
"""Tests for Responses API resource."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import Mock, patch

import pytest
import respx
from httpx import Response

from bud.client import BudClient


@pytest.fixture
def sample_responses_response() -> dict[str, Any]:
    """Sample Responses API response matching openai.types.responses.Response."""
    return {
        "id": "resp_abc123",
        "object": "response",
        "created_at": 1700000000,
        "model": "gpt-4.1",
        "status": "completed",
        "output": [
            {
                "type": "message",
                "id": "msg_001",
                "status": "completed",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": "The capital of France is Paris.",
                        "annotations": [],
                    }
                ],
            }
        ],
        "usage": {
            "input_tokens": 12,
            "output_tokens": 8,
            "total_tokens": 20,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 0},
        },
        "text": {"format": {"type": "text"}},
        "parallel_tool_calls": True,
        "tool_choice": "auto",
        "tools": [],
        "top_p": 1.0,
        "temperature": 1.0,
        "max_output_tokens": None,
        "truncation": "disabled",
        "metadata": {},
    }


# Non-streaming tests


@respx.mock
def test_create_response_non_streaming(
    client: BudClient,
    base_url: str,
    sample_responses_response: dict[str, Any],
) -> None:
    """Test creating a non-streaming response."""
    respx.post(f"{base_url}/v1/responses").mock(
        return_value=Response(200, json=sample_responses_response)
    )

    with patch("bud.resources.inference.Response") as MockResponse:
        MockResponse.model_validate.return_value = Mock(
            id="resp_abc123",
            model="gpt-4.1",
            status="completed",
            output_text="The capital of France is Paris.",
        )

        result = client.responses.create(
            model="gpt-4.1",
            input="What is the capital of France?",
        )

        assert result.id == "resp_abc123"
        assert result.model == "gpt-4.1"
        MockResponse.model_validate.assert_called_once()


@respx.mock
def test_create_response_with_all_params(
    client: BudClient,
    base_url: str,
    sample_responses_response: dict[str, Any],
) -> None:
    """Test that all optional params are included in the request payload."""
    route = respx.post(f"{base_url}/v1/responses").mock(
        return_value=Response(200, json=sample_responses_response)
    )

    with patch("bud.resources.inference.Response") as MockResponse:
        MockResponse.model_validate.return_value = Mock()

        client.responses.create(
            model="gpt-4.1",
            input="Hello",
            instructions="Be helpful",
            temperature=0.7,
            top_p=0.9,
            max_output_tokens=100,
            user="user-123",
            previous_response_id="resp_prev",
            store=True,
            service_tier="default",
        )

    request = route.calls.last.request
    payload = json.loads(request.content)
    assert payload["model"] == "gpt-4.1"
    assert payload["input"] == "Hello"
    assert payload["instructions"] == "Be helpful"
    assert payload["temperature"] == 0.7
    assert payload["top_p"] == 0.9
    assert payload["max_output_tokens"] == 100
    assert payload["user"] == "user-123"
    assert payload["previous_response_id"] == "resp_prev"
    assert payload["store"] is True
    assert payload["service_tier"] == "default"


def test_create_response_requires_model_or_prompt(client: BudClient) -> None:
    """Test that ValueError is raised if neither model nor prompt is provided."""
    with pytest.raises(ValueError, match="At least one of 'model' or 'prompt'"):
        client.responses.create(input="Hello")


@respx.mock
def test_create_response_with_prompt_param(
    client: BudClient,
    base_url: str,
    sample_responses_response: dict[str, Any],
) -> None:
    """Test that prompt param works without model."""
    route = respx.post(f"{base_url}/v1/responses").mock(
        return_value=Response(200, json=sample_responses_response)
    )

    with patch("bud.resources.inference.Response") as MockResponse:
        MockResponse.model_validate.return_value = Mock()
        client.responses.create(
            prompt={"id": "prompt_abc"},
            input="Hello",
        )

    request = route.calls.last.request
    payload = json.loads(request.content)
    assert payload["prompt"] == {"id": "prompt_abc"}
    assert "model" not in payload


# Error tests


@respx.mock
def test_create_response_401(client: BudClient, base_url: str) -> None:
    """Test 401 error mapping."""
    from bud.exceptions import AuthenticationError

    respx.post(f"{base_url}/v1/responses").mock(
        return_value=Response(401, json={"error": "Invalid API key"})
    )
    with pytest.raises(AuthenticationError):
        client.responses.create(model="gpt-4.1", input="Hello")


@respx.mock
def test_create_response_404(client: BudClient, base_url: str) -> None:
    """Test 404 error mapping."""
    from bud.exceptions import NotFoundError

    respx.post(f"{base_url}/v1/responses").mock(
        return_value=Response(404, json={"error": "Model not found"})
    )
    with pytest.raises(NotFoundError):
        client.responses.create(model="nonexistent", input="Hello")


@respx.mock
def test_create_response_422(client: BudClient, base_url: str) -> None:
    """Test 422 error mapping."""
    from bud.exceptions import ValidationError

    respx.post(f"{base_url}/v1/responses").mock(
        return_value=Response(422, json={"message": "Invalid params", "errors": []})
    )
    with pytest.raises(ValidationError):
        client.responses.create(model="gpt-4.1", input="Hello")


@respx.mock
def test_create_response_429(client: BudClient, base_url: str) -> None:
    """Test 429 error mapping."""
    from bud.exceptions import RateLimitError

    respx.post(f"{base_url}/v1/responses").mock(
        return_value=Response(429, json={"error": "Rate limited"})
    )
    with pytest.raises(RateLimitError):
        client.responses.create(model="gpt-4.1", input="Hello")


@respx.mock
def test_create_response_500(client: BudClient, base_url: str) -> None:
    """Test 500 error mapping."""
    from bud.exceptions import BudError

    respx.post(f"{base_url}/v1/responses").mock(
        return_value=Response(500, json={"error": "Internal error"})
    )
    with pytest.raises(BudError, match="Server error"):
        client.responses.create(model="gpt-4.1", input="Hello")
```

---

## 11. `tests/unit/test_response_streaming.py` — NEW FILE

**File:** `tests/unit/test_response_streaming.py` (create new)

```python
"""Tests for ResponseStream and AsyncResponseStream."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, Mock, patch

import pytest

from bud._streaming import SSEParser


class TestResponseStream:
    """Tests for sync ResponseStream."""

    def test_basic_iteration(self):
        """Test that ResponseStream yields parsed events."""
        from bud._response_streaming import ResponseStream

        sse_lines = [
            'event: response.output_text.delta',
            'data: {"type":"response.output_text.delta","item_id":"item_1","output_index":0,"content_index":0,"delta":"Hello"}',
            '',
            'event: response.output_text.delta',
            'data: {"type":"response.output_text.delta","item_id":"item_1","output_index":0,"content_index":0,"delta":" world"}',
            '',
            'data: [DONE]',
            '',
        ]

        mock_response = Mock()
        mock_response.iter_lines.return_value = iter(sse_lines)
        mock_response.close = Mock()

        with patch("bud._response_streaming._get_event_adapter") as mock_adapter:
            adapter = Mock()
            mock_adapter.return_value = adapter
            adapter.validate_python.side_effect = [
                Mock(type="response.output_text.delta", delta="Hello"),
                Mock(type="response.output_text.delta", delta=" world"),
            ]

            stream = ResponseStream(mock_response)
            events = list(stream)

            assert len(events) == 2
            assert events[0].delta == "Hello"
            assert events[1].delta == " world"

    def test_completed_response_captured(self):
        """Test that response.completed event is captured."""
        from bud._response_streaming import ResponseStream

        completed_data = {
            "type": "response.completed",
            "response": {"id": "resp_123", "status": "completed"},
        }

        sse_lines = [
            'event: response.completed',
            f'data: {json.dumps(completed_data)}',
            '',
            'data: [DONE]',
            '',
        ]

        mock_response = Mock()
        mock_response.iter_lines.return_value = iter(sse_lines)
        mock_response.close = Mock()

        mock_completed = Mock(type="response.completed")
        mock_completed.response = Mock(id="resp_123", status="completed")

        with patch("bud._response_streaming._get_event_adapter") as mock_adapter:
            adapter = Mock()
            mock_adapter.return_value = adapter
            adapter.validate_python.return_value = mock_completed

            stream = ResponseStream(mock_response)
            events = list(stream)

            assert len(events) == 1
            assert stream.completed_response is not None
            assert stream.completed_response.id == "resp_123"

    def test_done_sentinel_stops_iteration(self):
        """Test that [DONE] stops iteration."""
        from bud._response_streaming import ResponseStream

        sse_lines = [
            'data: {"type":"response.output_text.delta","delta":"Hi"}',
            '',
            'data: [DONE]',
            '',
            'data: {"type":"response.output_text.delta","delta":"ignored"}',
            '',
        ]

        mock_response = Mock()
        mock_response.iter_lines.return_value = iter(sse_lines)
        mock_response.close = Mock()

        with patch("bud._response_streaming._get_event_adapter") as mock_adapter:
            adapter = Mock()
            mock_adapter.return_value = adapter
            adapter.validate_python.return_value = Mock(type="response.output_text.delta")

            stream = ResponseStream(mock_response)
            events = list(stream)

            # Only 1 event before [DONE]
            assert len(events) == 1

    def test_json_parse_error_skipped(self):
        """Test that JSON parse errors are logged and skipped."""
        from bud._response_streaming import ResponseStream

        sse_lines = [
            'data: not-valid-json',
            '',
            'data: {"type":"response.output_text.delta","delta":"OK"}',
            '',
            'data: [DONE]',
            '',
        ]

        mock_response = Mock()
        mock_response.iter_lines.return_value = iter(sse_lines)
        mock_response.close = Mock()

        with patch("bud._response_streaming._get_event_adapter") as mock_adapter:
            adapter = Mock()
            mock_adapter.return_value = adapter
            adapter.validate_python.return_value = Mock(type="response.output_text.delta")

            stream = ResponseStream(mock_response)
            events = list(stream)

            # Only the valid event
            assert len(events) == 1

    def test_context_manager(self):
        """Test context manager closes stream."""
        from bud._response_streaming import ResponseStream

        mock_response = Mock()
        mock_response.iter_lines.return_value = iter([])
        mock_response.close = Mock()

        stream = ResponseStream(mock_response)
        with stream as s:
            assert s is stream
        mock_response.close.assert_called()

    def test_close_releases_response_context(self):
        """Test that close() exits the response context manager."""
        from bud._response_streaming import ResponseStream

        mock_response = Mock()
        mock_response.close = Mock()
        mock_ctx = Mock()

        stream = ResponseStream(mock_response, response_context=mock_ctx)
        stream.close()

        mock_response.close.assert_called_once()
        mock_ctx.__exit__.assert_called_once_with(None, None, None)
```

---

## 12. `tests/test_observability/test_responses_tracker.py` — NEW FILE

**File:** `tests/test_observability/test_responses_tracker.py` (create new)

```python
"""Unit tests for _responses_tracker module."""

from __future__ import annotations

import json
from unittest.mock import Mock

from bud.observability._genai_attributes import (
    BUD_INFERENCE_RESPONSE_OUTPUT_TEXT,
    BUD_RESPONSES_REQUEST_INPUT,
    BUD_RESPONSES_REQUEST_INSTRUCTIONS,
    GENAI_CONVERSATION_ID,
    GENAI_RESPONSE_CREATED,
    GENAI_RESPONSE_ID,
    GENAI_RESPONSE_MODEL,
    GENAI_RESPONSE_STATUS,
    GENAI_USAGE_INPUT_TOKENS,
    GENAI_USAGE_OUTPUT_TOKENS,
    GENAI_USAGE_TOTAL_TOKENS,
    RESPONSES_SAFE_INPUT_FIELDS,
    RESPONSES_SAFE_OUTPUT_FIELDS,
)
from bud.observability._responses_tracker import (
    _extract_responses_request_attrs,
    _extract_responses_response_attrs,
    _resolve_fields,
    track_responses,
)


# ---------------------------------------------------------------------------
# _resolve_fields
# ---------------------------------------------------------------------------


class TestResolveFields:
    def test_true_returns_safe_defaults(self):
        result = _resolve_fields(True, RESPONSES_SAFE_INPUT_FIELDS)
        assert result is RESPONSES_SAFE_INPUT_FIELDS

    def test_false_returns_none(self):
        result = _resolve_fields(False, RESPONSES_SAFE_INPUT_FIELDS)
        assert result is None

    def test_list_returns_frozenset(self):
        result = _resolve_fields(["model", "input"], RESPONSES_SAFE_INPUT_FIELDS)
        assert result == frozenset({"model", "input"})
        assert isinstance(result, frozenset)


# ---------------------------------------------------------------------------
# _extract_responses_request_attrs
# ---------------------------------------------------------------------------


class TestExtractResponsesRequestAttrs:
    def test_basic_params(self):
        kwargs = {"model": "gpt-4.1", "temperature": 0.7}
        result = _extract_responses_request_attrs(kwargs, RESPONSES_SAFE_INPUT_FIELDS)
        assert result["gen_ai.request.model"] == "gpt-4.1"
        assert result["gen_ai.request.temperature"] == 0.7

    def test_input_string_not_json_serialized(self):
        kwargs = {"input": "Hello world"}
        fields = frozenset({"input"})
        result = _extract_responses_request_attrs(kwargs, fields)
        assert result[BUD_RESPONSES_REQUEST_INPUT] == "Hello world"

    def test_input_list_json_serialized(self):
        kwargs = {"input": [{"role": "user", "content": "Hello"}]}
        fields = frozenset({"input"})
        result = _extract_responses_request_attrs(kwargs, fields)
        parsed = json.loads(result[BUD_RESPONSES_REQUEST_INPUT])
        assert parsed[0]["role"] == "user"

    def test_instructions_captured(self):
        kwargs = {"instructions": "Be helpful"}
        fields = frozenset({"instructions"})
        result = _extract_responses_request_attrs(kwargs, fields)
        assert result[BUD_RESPONSES_REQUEST_INSTRUCTIONS] == "Be helpful"

    def test_tools_json_serialized(self):
        kwargs = {"tools": [{"type": "function", "function": {"name": "get_weather"}}]}
        fields = frozenset({"tools"})
        result = _extract_responses_request_attrs(kwargs, fields)
        parsed = json.loads(result["bud.inference.request.tools"])
        assert parsed[0]["type"] == "function"

    def test_tool_choice_dict_serialized(self):
        kwargs = {"tool_choice": {"type": "function", "function": {"name": "get_weather"}}}
        fields = frozenset({"tool_choice"})
        result = _extract_responses_request_attrs(kwargs, fields)
        parsed = json.loads(result["bud.inference.request.tool_choice"])
        assert parsed["type"] == "function"

    def test_tool_choice_string_not_serialized(self):
        kwargs = {"tool_choice": "auto"}
        fields = frozenset({"tool_choice"})
        result = _extract_responses_request_attrs(kwargs, fields)
        assert result["bud.inference.request.tool_choice"] == "auto"

    def test_previous_response_id_mapped(self):
        kwargs = {"previous_response_id": "resp_prev_123"}
        fields = frozenset({"previous_response_id"})
        result = _extract_responses_request_attrs(kwargs, fields)
        assert result[GENAI_CONVERSATION_ID] == "resp_prev_123"

    def test_none_fields_returns_empty(self):
        result = _extract_responses_request_attrs({"model": "gpt-4.1"}, None)
        assert result == {}


# ---------------------------------------------------------------------------
# _extract_responses_response_attrs
# ---------------------------------------------------------------------------


def _mock_responses_response(
    id: str = "resp_123",
    model: str = "gpt-4.1",
    status: str = "completed",
    created_at: float = 1700000000.0,
    input_tokens: int = 10,
    output_tokens: int = 5,
    total_tokens: int = 15,
    output_text: str = "Hello!",
):
    """Create a mock openai.types.responses.Response-like object."""
    usage = Mock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens
    usage.total_tokens = total_tokens

    response = Mock()
    response.id = id
    response.model = model
    response.status = status
    response.created_at = created_at
    response.usage = usage
    response.output_text = output_text
    return response


class TestExtractResponsesResponseAttrs:
    def test_full_extraction(self):
        response = _mock_responses_response()
        result = _extract_responses_response_attrs(response, RESPONSES_SAFE_OUTPUT_FIELDS)
        assert result[GENAI_RESPONSE_ID] == "resp_123"
        assert result[GENAI_RESPONSE_MODEL] == "gpt-4.1"
        assert result[GENAI_RESPONSE_STATUS] == "completed"
        assert result[GENAI_RESPONSE_CREATED] == 1700000000.0
        assert result[GENAI_USAGE_INPUT_TOKENS] == 10
        assert result[GENAI_USAGE_OUTPUT_TOKENS] == 5
        assert result[GENAI_USAGE_TOTAL_TOKENS] == 15
        assert result[BUD_INFERENCE_RESPONSE_OUTPUT_TEXT] == "Hello!"

    def test_none_usage(self):
        response = _mock_responses_response()
        response.usage = None
        result = _extract_responses_response_attrs(response, RESPONSES_SAFE_OUTPUT_FIELDS)
        assert GENAI_USAGE_INPUT_TOKENS not in result

    def test_none_output_text(self):
        response = _mock_responses_response()
        response.output_text = None
        result = _extract_responses_response_attrs(response, RESPONSES_SAFE_OUTPUT_FIELDS)
        assert BUD_INFERENCE_RESPONSE_OUTPUT_TEXT not in result

    def test_none_fields_returns_empty(self):
        response = _mock_responses_response()
        result = _extract_responses_response_attrs(response, None)
        assert result == {}

    def test_selective_fields(self):
        response = _mock_responses_response()
        fields = frozenset({"id", "usage"})
        result = _extract_responses_response_attrs(response, fields)
        assert result[GENAI_RESPONSE_ID] == "resp_123"
        assert result[GENAI_USAGE_INPUT_TOKENS] == 10
        assert GENAI_RESPONSE_MODEL not in result
        assert GENAI_RESPONSE_STATUS not in result

    def test_datetime_created_at(self):
        """Test that datetime objects are converted to float timestamps."""
        response = _mock_responses_response()
        mock_dt = Mock()
        mock_dt.timestamp.return_value = 1700000000.0
        response.created_at = mock_dt
        fields = frozenset({"created_at"})
        result = _extract_responses_response_attrs(response, fields)
        assert result[GENAI_RESPONSE_CREATED] == 1700000000.0


# ---------------------------------------------------------------------------
# track_responses — idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_second_call_is_noop(self):
        client = Mock()
        client.responses.create = Mock(return_value="original")
        client.responses._bud_tracked = False

        result = track_responses(client)
        assert result is client
        first_create = client.responses.create

        assert client.responses._bud_tracked is True

        result2 = track_responses(client)
        assert result2 is client
        assert client.responses.create is first_create
```

---

## 13. `tests/test_observability/test_responses_integration.py` — NEW FILE

**File:** `tests/test_observability/test_responses_integration.py` (create new)

```python
"""Integration tests for track_responses() — full span lifecycle."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from bud.observability._genai_attributes import (
    BUD_INFERENCE_CHUNKS,
    BUD_INFERENCE_OPERATION,
    BUD_INFERENCE_RESPONSE_OUTPUT_TEXT,
    BUD_INFERENCE_STREAM,
    BUD_INFERENCE_STREAM_COMPLETED,
    BUD_INFERENCE_TTFT_MS,
    GENAI_OPERATION_NAME,
    GENAI_RESPONSE_ID,
    GENAI_RESPONSE_MODEL,
    GENAI_RESPONSE_STATUS,
    GENAI_SYSTEM,
    GENAI_USAGE_INPUT_TOKENS,
    GENAI_USAGE_OUTPUT_TOKENS,
    GENAI_USAGE_TOTAL_TOKENS,
)
from bud.observability._responses_tracker import track_responses


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def traced_env():
    """Set up a traced environment with InMemorySpanExporter."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    def _get_tracer(name="bud"):
        return provider.get_tracer(name)

    with (
        patch("bud.observability._track._is_noop", return_value=False),
        patch("bud.observability.get_tracer", side_effect=_get_tracer),
        patch("bud.observability._responses_tracker._is_noop", return_value=False),
    ):
        yield exporter, provider

    provider.shutdown()


def _make_client(create_return_value=None):
    """Create a mock BudClient with responses.create()."""
    client = Mock()
    client.responses = Mock()
    client.responses.create = Mock(return_value=create_return_value)
    client.responses._bud_tracked = False
    return client


def _make_response():
    """Create a realistic mock openai.types.responses.Response."""
    usage = Mock()
    usage.input_tokens = 10
    usage.output_tokens = 5
    usage.total_tokens = 15

    response = Mock()
    response.id = "resp_test"
    response.model = "gpt-4.1"
    response.status = "completed"
    response.created_at = 1700000000.0
    response.usage = usage
    response.output_text = "Hello!"
    return response


def _make_stream_events(texts, with_completed=True):
    """Create a list of mock stream events with an optional response.completed event."""
    events = []
    for text in texts:
        event = Mock()
        event.type = "response.output_text.delta"
        event.delta = text
        events.append(event)

    if with_completed:
        completed_event = Mock()
        completed_event.type = "response.completed"
        completed_event.response = _make_response()
        events.append(completed_event)

    return events


def _make_mock_stream(events):
    """Create a mock ResponseStream that yields events and has completed_response."""
    stream = Mock()
    stream.__iter__ = Mock(return_value=iter(events))

    # Find the completed response from events
    completed = None
    for e in events:
        if getattr(e, "type", None) == "response.completed":
            completed = e.response
            break
    stream.completed_response = completed
    return stream


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNonStreamingSpan:
    def test_span_created_with_correct_attributes(self, traced_env):
        exporter, _provider = traced_env
        response = _make_response()
        client = _make_client(create_return_value=response)
        track_responses(client)

        result = client.responses.create(
            model="gpt-4.1", input="Hello"
        )

        assert result is response
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "responses"
        attrs = dict(span.attributes)
        assert attrs[GENAI_SYSTEM] == "bud"
        assert attrs[BUD_INFERENCE_OPERATION] == "responses"
        assert attrs[GENAI_OPERATION_NAME] == "responses"
        assert attrs[BUD_INFERENCE_STREAM] is False
        assert attrs["gen_ai.request.model"] == "gpt-4.1"
        assert attrs[GENAI_RESPONSE_ID] == "resp_test"
        assert attrs[GENAI_RESPONSE_MODEL] == "gpt-4.1"
        assert attrs[GENAI_RESPONSE_STATUS] == "completed"
        assert attrs[GENAI_USAGE_INPUT_TOKENS] == 10
        assert attrs[GENAI_USAGE_OUTPUT_TOKENS] == 5
        assert attrs[GENAI_USAGE_TOTAL_TOKENS] == 15
        assert attrs[BUD_INFERENCE_RESPONSE_OUTPUT_TEXT] == "Hello!"
        assert span.status.status_code == StatusCode.OK


class TestStreamingSpan:
    def test_streaming_span_attributes(self, traced_env):
        exporter, _provider = traced_env
        events = _make_stream_events(["Hello", " ", "world"])
        stream = _make_mock_stream(events)
        client = _make_client(create_return_value=stream)
        track_responses(client)

        result_stream = client.responses.create(
            model="gpt-4.1", input="Hello", stream=True
        )

        collected = list(result_stream)
        # 3 text deltas + 1 response.completed
        assert len(collected) == 4

        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "responses.stream"
        attrs = dict(span.attributes)
        assert attrs[GENAI_SYSTEM] == "bud"
        assert attrs[BUD_INFERENCE_STREAM] is True
        assert attrs[BUD_INFERENCE_CHUNKS] == 4
        assert attrs[BUD_INFERENCE_STREAM_COMPLETED] is True
        assert BUD_INFERENCE_TTFT_MS in attrs
        assert attrs[BUD_INFERENCE_TTFT_MS] >= 0
        # Usage from completed_response
        assert attrs[GENAI_USAGE_INPUT_TOKENS] == 10
        assert attrs[GENAI_USAGE_OUTPUT_TOKENS] == 5
        assert span.status.status_code == StatusCode.OK

    def test_partial_streaming(self, traced_env):
        exporter, _provider = traced_env
        events = _make_stream_events(["a", "b", "c", "d"])
        stream = _make_mock_stream(events)
        client = _make_client(create_return_value=stream)
        track_responses(client)

        result_stream = client.responses.create(model="gpt-4.1", input="", stream=True)

        collected = []
        for event in result_stream:
            collected.append(event)
            if len(collected) == 2:
                break

        assert len(collected) == 2

        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        attrs = dict(span.attributes)
        assert attrs[BUD_INFERENCE_CHUNKS] == 2
        assert attrs[BUD_INFERENCE_STREAM_COMPLETED] is False
        assert span.status.status_code != StatusCode.ERROR


class TestErrorSpan:
    def test_error_recorded_and_reraised(self, traced_env):
        exporter, _provider = traced_env
        client = _make_client()
        client.responses.create.side_effect = RuntimeError("API error")
        track_responses(client)

        with pytest.raises(RuntimeError, match="API error"):
            client.responses.create(model="gpt-4.1", input="Hello")

        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.status.status_code == StatusCode.ERROR
        assert any(e.name == "exception" for e in span.events)


class TestFieldListMode:
    def test_capture_only_model(self, traced_env):
        exporter, _provider = traced_env
        response = _make_response()
        client = _make_client(create_return_value=response)
        track_responses(client, capture_input=["model"])

        client.responses.create(model="gpt-4.1", temperature=0.5, input="Hello")

        spans = exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs["gen_ai.request.model"] == "gpt-4.1"
        assert "gen_ai.request.temperature" not in attrs


class TestCaptureFalse:
    def test_no_input_output_attributes(self, traced_env):
        exporter, _provider = traced_env
        response = _make_response()
        client = _make_client(create_return_value=response)
        track_responses(client, capture_input=False, capture_output=False)

        client.responses.create(model="gpt-4.1", input="Hello")

        spans = exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        # Always-on attributes should be present
        assert attrs[GENAI_SYSTEM] == "bud"
        assert attrs[BUD_INFERENCE_OPERATION] == "responses"
        # Request/response attributes should NOT be present
        assert "gen_ai.request.model" not in attrs
        assert GENAI_RESPONSE_ID not in attrs
        assert GENAI_USAGE_INPUT_TOKENS not in attrs


class TestTrackNesting:
    def test_parent_child_with_track_decorator(self, traced_env):
        exporter, _provider = traced_env
        response = _make_response()
        client = _make_client(create_return_value=response)
        track_responses(client)

        from bud.observability._track import track

        @track(name="pipeline")
        def pipeline():
            return client.responses.create(model="gpt-4.1", input="Hello")

        pipeline()

        spans = exporter.get_finished_spans()
        assert len(spans) == 2

        resp_span = next(s for s in spans if s.name == "responses")
        pipeline_span = next(s for s in spans if s.name == "pipeline")

        assert resp_span.parent is not None
        assert resp_span.parent.span_id == pipeline_span.context.span_id
```

---

## Summary of All Changes

| # | File | Action | Lines Changed |
|---|------|--------|---------------|
| 1 | `pyproject.toml` | Modify | +1 line (add openai dep) |
| 2 | `src/bud/_http.py` | Modify | +2 imports, +35 lines (async_stream method) |
| 3 | `src/bud/_response_streaming.py` | **Create** | ~200 lines |
| 4 | `src/bud/resources/inference.py` | Modify | +3 imports, ~250 lines (Responses + AsyncResponses) |
| 5 | `src/bud/resources/__init__.py` | Modify | +2 imports, +2 exports |
| 6 | `src/bud/client.py` | Modify | +2 imports, +2 lines (self.responses) |
| 7 | `src/bud/observability/_genai_attributes.py` | Modify | +50 lines (constants) |
| 8 | `src/bud/observability/_responses_tracker.py` | **Create** | ~310 lines |
| 9 | `src/bud/observability/__init__.py` | Modify | +4 lines (__getattr__ + __all__) |
| 10 | `tests/unit/test_responses.py` | **Create** | ~200 lines |
| 11 | `tests/unit/test_response_streaming.py` | **Create** | ~180 lines |
| 12 | `tests/test_observability/test_responses_tracker.py` | **Create** | ~200 lines |
| 13 | `tests/test_observability/test_responses_integration.py` | **Create** | ~220 lines |
