# Plan: v1/responses Endpoint Support with OTel Observability

## Overview

Add support for the OpenAI Responses API (`/v1/responses`) to the BudAI SDK, including both sync and async clients, streaming support, and full OTel observability instrumentation via `track_responses()`.

## Scope

### New Files
- `src/bud/_response_streaming.py` — `ResponseStream` + `AsyncResponseStream`
- `src/bud/observability/_responses_tracker.py` — `track_responses()` + `TracedResponseStream`
- `tests/unit/test_responses.py` — Resource unit tests
- `tests/unit/test_response_streaming.py` — Streaming unit tests
- `tests/test_observability/test_responses_tracker.py` — Tracker unit tests
- `tests/test_observability/test_responses_integration.py` — Integration tests

### Modified Files
- `pyproject.toml` — Add `openai>=1.90.0` dependency
- `src/bud/_http.py` — Add `async_stream()` to `AsyncHttpClient`
- `src/bud/resources/inference.py` — Add `Responses` + `AsyncResponses` classes
- `src/bud/resources/__init__.py` — Export new classes
- `src/bud/client.py` — Wire `client.responses` into both clients
- `src/bud/observability/_genai_attributes.py` — Add Responses API constants
- `src/bud/observability/__init__.py` — Register `track_responses`

---

## Files to Modify

### 1. `pyproject.toml`
- Add `"openai>=1.90.0"` to `dependencies` array (line 36-44)
- This provides `openai.types.responses.Response`, `ResponseStreamEvent`, etc.

### 2. `src/bud/_http.py`
- Add `async_stream()` method to `AsyncHttpClient` (after line 364), mirroring sync `HttpClient.stream()`:
  - Use `@asynccontextmanager`
  - Use `self._client.stream(method, path, json=json, headers=headers, timeout=stream_timeout)` as async context manager
  - Check `response.is_success` before yielding
  - Set `Accept: text/event-stream` header and extended timeouts

### 3. `src/bud/_response_streaming.py` *(NEW)*
- `ResponseStream` — sync SSE stream for Responses API
  - Reuses `SSEParser` from `_streaming.py`
  - Uses `pydantic.TypeAdapter(ResponseStreamEvent)` to parse the discriminated union of 53 event types
  - Captures `response.completed` event's `Response` object in `self._completed_response` property
  - Handles both `[DONE]` sentinel and natural stream close
  - Context manager support (`__enter__`/`__exit__`)
- `AsyncResponseStream` — async version
  - Same design but uses `async for line in response.aiter_lines()`
  - Implements `__aiter__` instead of `__iter__`

### 4. `src/bud/resources/inference.py`
Add two new resource classes after existing code:

- **`Responses(SyncResource)`** with:
  - `create(*, model=None, input=None, stream=False, instructions=None, previous_response_id=None, temperature=None, top_p=None, max_output_tokens=None, tools=None, tool_choice=None, parallel_tool_calls=None, reasoning=None, metadata=None, user=None, prompt=None, store=None, background=None, service_tier=None, text=None, truncation=None, include=None) -> Response | ResponseStream`
  - Overloads for `stream: Literal[False]` -> `Response` and `stream: Literal[True]` -> `ResponseStream`
  - Validates that at least one of `model` or `prompt` is provided
  - Non-streaming: `self._http.post("/v1/responses", json=payload)` -> `Response.model_validate(data)`
  - Streaming: `self._http.stream("POST", "/v1/responses", json=payload)` -> `ResponseStream(...)`

- **`AsyncResponses(AsyncResource)`** with:
  - `async create(...)` same signature
  - Non-streaming: `await self._http.post("/v1/responses", json=payload)` -> `Response.model_validate(data)`
  - Streaming: `self._http.async_stream(...)` -> `AsyncResponseStream(...)`

### 5. `src/bud/resources/__init__.py`
- Add `Responses, AsyncResponses` to imports from `inference`
- Add to `__all__`

### 6. `src/bud/client.py`
- Import `Responses` and `AsyncResponses` from `bud.resources.inference`
- **BudClient.__init__** (line ~163): add `self.responses = Responses(self._http)`
- **AsyncBudClient.__init__** (line ~371): add `self.responses = AsyncResponses(self._http)`

### 7. `src/bud/observability/_genai_attributes.py`
Add new constant block after existing chat constants:

```python
# Responses API attributes
GENAI_OPERATION_NAME = "gen_ai.operation.name"
GENAI_CONVERSATION_ID = "gen_ai.conversation.id"
GENAI_RESPONSE_STATUS = "gen_ai.response.status"
BUD_INFERENCE_RESPONSE_OUTPUT_TEXT = "bud.inference.response.output_text"
BUD_RESPONSES_REQUEST_INPUT = "bud.inference.request.input"
BUD_RESPONSES_REQUEST_INSTRUCTIONS = "bud.inference.request.instructions"
BUD_RESPONSES_REQUEST_PROMPT = "bud.inference.request.prompt"

RESPONSES_INPUT_ATTR_MAP: dict[str, str] = { ... }
RESPONSES_DEFAULT_INPUT_FIELDS: frozenset[str] = frozenset({ ... })
RESPONSES_DEFAULT_OUTPUT_FIELDS: frozenset[str] = frozenset({ ... })
RESPONSES_SAFE_INPUT_FIELDS = RESPONSES_DEFAULT_INPUT_FIELDS
RESPONSES_SAFE_OUTPUT_FIELDS = RESPONSES_DEFAULT_OUTPUT_FIELDS
```

### 8. `src/bud/observability/_responses_tracker.py` *(NEW)*
Following the exact pattern of `_inference_tracker.py`:

- **`track_responses(client, *, capture_input=True, capture_output=True, span_name="responses") -> BudClient`**
  - Idempotency guard via `client.responses._bud_tracked`
  - Monkey-patches `client.responses.create`
  - Sets always-on attributes: `gen_ai.system=bud`, `bud.inference.operation=responses`, `gen_ai.operation.name=responses`
  - Maps `previous_response_id` -> `gen_ai.conversation.id`

- **`_extract_responses_request_attrs(kwargs, fields)`** — maps create() kwargs to OTel attributes. Serializes complex types (input lists, tools, prompt dicts) as JSON strings.

- **`_extract_responses_response_attrs(response, fields)`** — extracts from `openai.types.responses.Response`:
  - `id` -> `gen_ai.response.id`
  - `model` -> `gen_ai.response.model`
  - `status` -> `gen_ai.response.status`
  - `created_at` -> `gen_ai.response.created` (float)
  - `usage.input_tokens/output_tokens/total_tokens` -> standard OTel token attrs
  - `output_text` -> `bud.inference.response.output_text`

- **`TracedResponseStream`** — wrapper for streaming with span lifecycle:
  - TTFT tracking on first event
  - Chunk counting
  - On finalization: reads `self._inner.completed_response` (the full Response from `response.completed` SSE event) for usage/output extraction
  - No need for chunk-by-chunk aggregation (unlike chat completions) — the `response.completed` event has everything

### 9. `src/bud/observability/__init__.py`
- Add `track_responses` to `__getattr__` lazy loader
- Add `track_responses` to `__all__`
- Update module docstring to mention `track_responses()`

---

## Files to Create (Tests)

### 10. `tests/unit/test_responses.py`
Test `Responses.create()`:
- Non-streaming: mock POST, verify `Response` returned with correct fields
- Streaming: mock SSE POST, verify `ResponseStream` yields event subtypes
- All optional params present in payload
- `prompt` parameter pass-through
- Validation: neither `model` nor `prompt` -> ValueError
- Error mapping (401, 404, 422, 429, 500)

### 11. `tests/unit/test_response_streaming.py`
Test `ResponseStream` and `AsyncResponseStream`:
- Basic iteration yields correctly-typed `ResponseStreamEvent` subtypes
- `completed_response` property captured from `response.completed` event
- `[DONE]` sentinel handling
- Stream close without `[DONE]`
- JSON parse error -> logged and skipped
- Validation error -> logged and skipped
- Context manager cleanup

### 12. `tests/test_observability/test_responses_tracker.py`
Unit tests mirroring `test_inference_tracker.py`:
- `_resolve_fields` for True/False/list
- `_extract_responses_request_attrs` for all parameter types
- `_extract_responses_response_attrs` for full/partial/None fields
- `track_responses` idempotency
- Attribute mapping correctness

### 13. `tests/test_observability/test_responses_integration.py`
Integration tests mirroring `test_inference_integration.py`:
- Non-streaming span with correct attributes and status
- Streaming span with TTFT, chunk count, stream_completed
- Error span recorded and reraised
- Partial streaming (early break)
- Selective field capture
- `capture_input=False, capture_output=False`
- Parent-child span nesting with `@track`

---

## Key Design Details

### Streaming Architecture

The Responses API SSE format uses named events:
```
event: response.output_text.delta
data: {"type":"response.output_text.delta","delta":"Hello","item_id":"item_1",...}

event: response.completed
data: {"type":"response.completed","response":{...full Response with usage...}}
```

The existing `SSEParser` in `_streaming.py` already parses both `event:` and `data:` fields correctly. The `ResponseStream` reuses `SSEParser` and uses `pydantic.TypeAdapter(ResponseStreamEvent)` to parse the discriminated union (53 event types, discriminated by `type` field in the JSON data).

**Key insight:** The `response.completed` event contains the full `Response` object with `usage` data. The `ResponseStream` captures this in `self._completed_response` so observability can extract token counts without reconstructing from deltas.

### Why not extend existing `Stream[T]`?

The existing `Stream[T]` assumes a single model class for all events. The Responses API yields a discriminated union of 53 types. Creating a separate `ResponseStream` keeps both implementations simple and independent.

### Async Streaming

`AsyncHttpClient` currently lacks a `stream()` method. We add `async_stream()` as an `@asynccontextmanager` that uses `httpx.AsyncClient.stream()`. The `AsyncResponseStream` mirrors `ResponseStream` but uses `async for line in response.aiter_lines()`.

### openai Types Used

All from `openai.types.responses`:
- `Response` — non-streaming return type (Pydantic v2 model with `output_text` property)
- `ResponseStreamEvent` — discriminated union type alias for 53 event types
- `ResponseCompletedEvent` — has `response: Response` field
- `ResponseTextDeltaEvent` — has `delta: str` field
- `ResponseUsage` — `input_tokens`, `output_tokens`, `total_tokens` + details

---

## Implementation Order

1. `pyproject.toml` — add openai dep
2. `src/bud/_http.py` — add `async_stream()` to `AsyncHttpClient`
3. `src/bud/_response_streaming.py` — `ResponseStream` + `AsyncResponseStream`
4. `src/bud/resources/inference.py` — `Responses` + `AsyncResponses` classes
5. `src/bud/resources/__init__.py` — exports
6. `src/bud/client.py` — wire into BudClient + AsyncBudClient
7. `tests/unit/test_responses.py` — resource tests
8. `tests/unit/test_response_streaming.py` — streaming tests
9. `src/bud/observability/_genai_attributes.py` — add constants
10. `src/bud/observability/_responses_tracker.py` — tracker
11. `src/bud/observability/__init__.py` — register
12. `tests/test_observability/test_responses_tracker.py` — tracker unit tests
13. `tests/test_observability/test_responses_integration.py` — integration tests

## Verification

```bash
cd /home/budadmin/varunsr/BudAIFoundry-SDK

# Run all tests
python3 -m pytest tests/ -v

# Run only new tests
python3 -m pytest tests/unit/test_responses.py tests/unit/test_response_streaming.py tests/test_observability/test_responses_tracker.py tests/test_observability/test_responses_integration.py -v

# Run existing tests to verify no regressions
python3 -m pytest tests/unit/test_client.py tests/test_observability/ -v

# Type check
mypy src/bud/resources/inference.py src/bud/_response_streaming.py src/bud/observability/_responses_tracker.py

# Lint
ruff check src/bud/ tests/
```
