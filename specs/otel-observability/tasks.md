# Implementation Tasks: v1/responses Endpoint + `track_responses()`

## Dependency Graph

```
TASK-1 (pyproject.toml)
  │
  └──→ TASK-2 (async_stream) ──→ TASK-3 (_response_streaming.py)
                                    │
                                    └──→ TASK-4 (Responses resource) ──→ TASK-5 (exports) ──→ TASK-6 (client.py)
                                                                                                │
                                                                                                ├──→ TASK-7 (test_responses.py)
                                                                                                ├──→ TASK-8 (test_response_streaming.py)
                                                                                                │
                                                                                                └──→ TASK-9 (_genai_attributes.py)
                                                                                                       │
                                                                                                       └──→ TASK-10 (_responses_tracker.py)
                                                                                                              │
                                                                                                              └──→ TASK-11 (observability/__init__.py)
                                                                                                                     │
                                                                                                                     ├──→ TASK-12 (test_responses_tracker.py)
                                                                                                                     └──→ TASK-13 (test_responses_integration.py)
```

---

## TASK-1: Add openai dependency to `pyproject.toml`

**Description:** Add `openai>=1.90.0` to the project dependencies. This provides `openai.types.responses.Response`, `ResponseStreamEvent`, `ResponseCompletedEvent`, and other types needed for the Responses API.

**Files:**
- `pyproject.toml` (modify — add dependency to `dependencies` array, lines 36-44)

**Scope:**
- Add `"openai>=1.90.0"` to the `dependencies` array
- This is the only change in this file

**Acceptance Criteria:**
- [x] `"openai>=1.90.0"` appears in the `dependencies` array in `pyproject.toml`
- [x] `pip install -e .` succeeds and installs openai
- [x] `python -c "from openai.types.responses import Response, ResponseStreamEvent"` succeeds
- [x] `ruff check pyproject.toml` passes

**Depends On:** None

---

## TASK-2: Add `async_stream()` to `AsyncHttpClient`

**Description:** Add an `async_stream()` method to `AsyncHttpClient` that mirrors the sync `HttpClient.stream()` method. This enables SSE streaming for async clients, which `AsyncResponseStream` requires.

**Files:**
- `src/bud/_http.py` (modify — add method to `AsyncHttpClient` class, after line ~364)

**Scope:**
- Add `from contextlib import asynccontextmanager` import (if not present)
- Add `from collections.abc import AsyncIterator` import (if not present)
- Implement `async_stream(self, method: str, path: str, *, json: dict | None = None, headers: dict | None = None) -> AsyncIterator[httpx.Response]`:
  - Use `@asynccontextmanager` decorator
  - Set `Accept: text/event-stream` header
  - Use extended timeout: `httpx.Timeout(connect=10.0, read=300.0, write=10.0, pool=10.0)`
  - Use `async with self._client.stream(method, path, json=json, headers=headers, timeout=stream_timeout) as response:`
  - Check `response.is_success` — if not, `await response.aread()` and call `self._handle_error_response(response)`
  - Yield the raw `httpx.Response` on success

**Acceptance Criteria:**
- [x] `AsyncHttpClient` has an `async_stream()` method
- [x] Method sets `Accept: text/event-stream` header
- [x] Method uses extended read timeout (300s)
- [x] Non-success responses raise mapped errors via `_handle_error_response()`
- [x] Success responses yield raw `httpx.Response`
- [x] Method uses `@asynccontextmanager`
- [x] `ruff check src/bud/_http.py` passes

**Depends On:** TASK-1

---

## TASK-3: Create `_response_streaming.py` — ResponseStream + AsyncResponseStream

**Description:** Create the new streaming module that provides `ResponseStream` (sync) and `AsyncResponseStream` (async) for the Responses API SSE stream. These parse the discriminated union of ~53 event types using `pydantic.TypeAdapter(ResponseStreamEvent)`.

**Files:**
- `src/bud/_response_streaming.py` (create)

**Scope:**
- **`ResponseStream`** (sync):
  - `__init__(self, response: httpx.Response)` — stores response, creates `SSEParser`, creates `TypeAdapter(ResponseStreamEvent)`, initializes `_completed_response = None`
  - `__iter__(self)` — iterates over `response.iter_lines()`, feeds to SSEParser, parses data-only lines via TypeAdapter, captures `ResponseCompletedEvent.response` in `_completed_response`, handles `[DONE]` sentinel, logs and skips JSON/validation errors
  - `completed_response` property — returns captured `Response` or `None`
  - `__enter__` / `__exit__` / `close()` — context manager that closes underlying response
- **`AsyncResponseStream`** (async):
  - Same design but uses `async for line in response.aiter_lines()`
  - Implements `__aiter__` / `__anext__` instead of `__iter__`
  - `__aenter__` / `__aexit__` / `async close()` — async context manager
- Imports: `SSEParser` from `bud._streaming`, `ResponseStreamEvent` / `ResponseCompletedEvent` / `Response` from `openai.types.responses`, `TypeAdapter` from `pydantic`

**Acceptance Criteria:**
- [x] `ResponseStream` iterates SSE lines and yields `ResponseStreamEvent` subtypes
- [x] `ResponseCompletedEvent` is detected and its `.response` stored in `completed_response`
- [x] `[DONE]` sentinel stops iteration cleanly
- [x] JSON parse errors are logged and skipped (not raised)
- [x] Pydantic validation errors are logged and skipped
- [x] `AsyncResponseStream` works with `async for event in stream:`
- [x] Both support context manager protocol
- [x] `close()` / `async close()` closes the underlying `httpx.Response`
- [x] `ruff check src/bud/_response_streaming.py` passes

**Depends On:** TASK-2

---

## TASK-4: Add `Responses` + `AsyncResponses` resource classes

**Description:** Add two new resource classes to `inference.py` following the existing `ChatCompletions` pattern. These expose `client.responses.create()` for both sync and async clients.

**Files:**
- `src/bud/resources/inference.py` (modify — add classes after existing code)

**Scope:**
- **`Responses(SyncResource)`**:
  - `create(*, model=None, input=None, stream=False, instructions=None, previous_response_id=None, temperature=None, top_p=None, max_output_tokens=None, tools=None, tool_choice=None, parallel_tool_calls=None, reasoning=None, metadata=None, user=None, prompt=None, store=None, background=None, service_tier=None, text=None, truncation=None, include=None) -> Response | ResponseStream`
  - `@overload` for `stream: Literal[False]` -> `Response` and `stream: Literal[True]` -> `ResponseStream`
  - Validates at least one of `model` or `prompt` is provided (raises `ValueError`)
  - Builds payload dict, filtering `None` values
  - Non-streaming: `self._http.post("/v1/responses", json=payload)` -> `Response.model_validate(data)`
  - Streaming: `self._http.stream("POST", "/v1/responses", json=payload)` -> `ResponseStream(raw_response)`
- **`AsyncResponses(AsyncResource)`**:
  - Same signature with `async create(...)`
  - Non-streaming: `await self._http.post(...)` -> `Response.model_validate(data)`
  - Streaming: `self._http.async_stream(...)` -> `AsyncResponseStream(raw_response)`
- Add imports: `Response` from `openai.types.responses`, `ResponseStream` / `AsyncResponseStream` from `bud._response_streaming`, `overload` / `Literal` from `typing`

**Acceptance Criteria:**
- [x] `Responses` class extends `SyncResource`
- [x] `AsyncResponses` class extends `AsyncResource`
- [x] `create()` has `@overload` decorators for stream True/False
- [x] `ValueError` raised when neither `model` nor `prompt` provided
- [x] Non-streaming returns `openai.types.responses.Response`
- [x] Streaming returns `ResponseStream` (sync) / `AsyncResponseStream` (async)
- [x] Payload excludes `None` values and `stream` when `False`
- [x] `stream=True` is included in the payload
- [x] All 21 optional parameters are accepted
- [x] `ruff check src/bud/resources/inference.py` passes

**Depends On:** TASK-3

---

## TASK-5: Export new classes from `resources/__init__.py`

**Description:** Add the new `Responses` and `AsyncResponses` classes to the resource module's public exports.

**Files:**
- `src/bud/resources/__init__.py` (modify)

**Scope:**
- Add `Responses, AsyncResponses` to the import from `.inference`
- Add `"Responses"`, `"AsyncResponses"` to `__all__`

**Acceptance Criteria:**
- [x] `from bud.resources import Responses, AsyncResponses` works
- [x] Both names appear in `bud.resources.__all__`
- [x] `ruff check src/bud/resources/__init__.py` passes

**Depends On:** TASK-4

---

## TASK-6: Wire `client.responses` into BudClient + AsyncBudClient

**Description:** Add `self.responses` resource to both client classes so users can call `client.responses.create(...)`.

**Files:**
- `src/bud/client.py` (modify)

**Scope:**
- Add `Responses` to the import from `bud.resources.inference` (line ~22)
- Add `AsyncResponses` to the import from `bud.resources.inference` (or same line)
- In `BudClient.__init__` (after line ~163): add `self.responses = Responses(self._http)`
- In `AsyncBudClient.__init__` (after line ~371): add `self.responses = AsyncResponses(self._http)`

**Acceptance Criteria:**
- [x] `BudClient(api_key="test").responses` is a `Responses` instance
- [x] `AsyncBudClient(api_key="test").responses` is an `AsyncResponses` instance
- [x] Existing resource attributes are unchanged
- [x] `ruff check src/bud/client.py` passes

**Depends On:** TASK-5

---

## TASK-7: Create `tests/unit/test_responses.py` — resource unit tests

**Description:** Write unit tests for the `Responses.create()` method covering non-streaming, streaming, parameter handling, and error cases.

**Files:**
- `tests/unit/test_responses.py` (create)

**Scope:**
- Test non-streaming: mock `HttpClient.post()` returning a dict, verify `Response` object returned with correct fields
- Test streaming: mock `HttpClient.stream()` returning SSE lines, verify `ResponseStream` yields events
- Test all optional params present in payload (no `None` values sent)
- Test `prompt` parameter pass-through
- Test validation: neither `model` nor `prompt` raises `ValueError`
- Test error mapping: mock HTTP 401/404/422/429/500 responses, verify correct exceptions raised
- Use `@respx.mock` or `unittest.mock` patterns matching existing `tests/unit/test_inference.py`

**Acceptance Criteria:**
- [x] All tests pass: `pytest tests/unit/test_responses.py -v`
- [x] Non-streaming create returns valid `Response` object
- [x] Streaming create returns `ResponseStream` that yields events
- [x] `ValueError` test covers missing model/prompt
- [x] Error mapping tests cover 401, 404, 422, 429, 500
- [x] No external API calls (fully mocked)
- [x] `ruff check tests/unit/test_responses.py` passes

**Depends On:** TASK-6

---

## TASK-8: Create `tests/unit/test_response_streaming.py` — streaming unit tests

**Description:** Write unit tests for `ResponseStream` and `AsyncResponseStream` covering event parsing, completed response capture, error handling, and cleanup.

**Files:**
- `tests/unit/test_response_streaming.py` (create)

**Scope:**
- Test basic iteration yields correctly-typed `ResponseStreamEvent` subtypes
- Test `completed_response` property captured from `response.completed` event
- Test `[DONE]` sentinel handling (iteration stops cleanly)
- Test stream close without `[DONE]` (natural end)
- Test JSON parse error is logged and skipped (not raised)
- Test pydantic validation error is logged and skipped
- Test context manager cleanup (`__exit__` / `__aexit__` closes response)
- Use mock `httpx.Response` with `iter_lines()` / `aiter_lines()` returning predefined SSE data

**Acceptance Criteria:**
- [x] All tests pass: `pytest tests/unit/test_response_streaming.py -v`
- [x] `ResponseStream` yields correct event types
- [x] `AsyncResponseStream` works with `async for`
- [x] `completed_response` is `None` before `response.completed` event, populated after
- [x] Malformed JSON lines don't crash iteration
- [x] Context manager calls `close()` on underlying response
- [x] `ruff check tests/unit/test_response_streaming.py` passes

**Depends On:** TASK-6

---

## TASK-9: Add Responses API constants to `_genai_attributes.py`

**Description:** Add OTel attribute constants, input/output field maps, and safe field sets for the Responses API. These parallel the existing `CHAT_*` constants.

**Files:**
- `src/bud/observability/_genai_attributes.py` (modify — add block after existing chat constants)

**Scope:**
- Add constants:
  - `GENAI_OPERATION_NAME = "gen_ai.operation.name"`
  - `GENAI_CONVERSATION_ID = "gen_ai.conversation.id"`
  - `GENAI_RESPONSE_STATUS = "gen_ai.response.status"`
  - `BUD_INFERENCE_RESPONSE_OUTPUT_TEXT = "bud.inference.response.output_text"`
  - `BUD_RESPONSES_REQUEST_INPUT = "bud.inference.request.input"`
  - `BUD_RESPONSES_REQUEST_INSTRUCTIONS = "bud.inference.request.instructions"`
  - `BUD_RESPONSES_REQUEST_PROMPT = "bud.inference.request.prompt"`
- Add `RESPONSES_INPUT_ATTR_MAP: dict[str, str]` mapping `create()` kwargs to OTel attribute keys:
  - `model` -> `gen_ai.request.model`, `temperature` -> `gen_ai.request.temperature`, `top_p` -> `gen_ai.request.top_p`, `max_output_tokens` -> `gen_ai.request.max_tokens`, `input` -> `bud.inference.request.input`, `instructions` -> `bud.inference.request.instructions`, `prompt` -> `bud.inference.request.prompt`, `tools` -> `gen_ai.request.tools`, `tool_choice` -> `gen_ai.request.tool_choice`
- Add `RESPONSES_DEFAULT_INPUT_FIELDS: frozenset[str]` — safe fields (model, temperature, top_p, max_output_tokens, tool_choice, reasoning, store, service_tier, previous_response_id)
- Add `RESPONSES_DEFAULT_OUTPUT_FIELDS: frozenset[str]` — safe fields (id, model, status, created_at, usage, output_text)
- Add `RESPONSES_SAFE_INPUT_FIELDS = RESPONSES_DEFAULT_INPUT_FIELDS`
- Add `RESPONSES_SAFE_OUTPUT_FIELDS = RESPONSES_DEFAULT_OUTPUT_FIELDS`

**Acceptance Criteria:**
- [x] All new constants are importable: `from bud.observability._genai_attributes import GENAI_OPERATION_NAME, RESPONSES_INPUT_ATTR_MAP, ...`
- [x] `RESPONSES_SAFE_INPUT_FIELDS` does NOT contain `input`, `instructions`, `tools`, `user` (PII-safe)
- [x] `RESPONSES_SAFE_OUTPUT_FIELDS` contains `id`, `model`, `status`, `created_at`, `usage`, `output_text`
- [x] `RESPONSES_INPUT_ATTR_MAP["model"]` == `"gen_ai.request.model"`
- [x] `RESPONSES_INPUT_ATTR_MAP["input"]` == `"bud.inference.request.input"`
- [x] `ruff check src/bud/observability/_genai_attributes.py` passes

**Depends On:** TASK-6

---

## TASK-10: Create `_responses_tracker.py` — `track_responses()` + `TracedResponseStream`

**Description:** Create the observability tracker for the Responses API, following the exact pattern of `_inference_tracker.py`. This monkey-patches `client.responses.create()` with OTel spans.

**Files:**
- `src/bud/observability/_responses_tracker.py` (create)

**Scope:**
- **`track_responses(client, *, capture_input=True, capture_output=True, span_name="responses") -> BudClient`**:
  - Idempotency guard via `client.responses._bud_tracked`
  - Save `original_create = client.responses.create`
  - Resolve field sets via `_resolve_fields()` from `_inference_tracker`
  - Define `traced_create(**kwargs)`:
    - `_is_noop()` fast path
    - Create span via `create_traced_span(effective_span_name, get_tracer("bud.inference"))`
    - Always-on attributes: `gen_ai.system=bud`, `bud.inference.operation=responses`, `gen_ai.operation.name=responses`, `bud.inference.stream=<bool>`
    - Map `previous_response_id` -> `gen_ai.conversation.id`
    - Extract request attributes
    - Call `original_create(**kwargs)`
    - Streaming: return `TracedResponseStream(result, span, token, output_fields)`
    - Non-streaming: extract response attrs, set OK, end span, detach context
  - Monkey-patch: `client.responses.create = traced_create`, set `_bud_tracked = True`

- **`_extract_responses_request_attrs(kwargs, fields)`**:
  - For each kwarg in `fields & kwargs.keys()`:
    - `input`, `tools`, `prompt` -> `json.dumps(value)` (complex types)
    - `tool_choice` -> `json.dumps()` if not str, else direct
    - Scalars -> direct value
    - Lookup key in `RESPONSES_INPUT_ATTR_MAP`, fallback to `bud.inference.request.{name}`

- **`_extract_responses_response_attrs(response, fields)`**:
  - `id` -> `gen_ai.response.id`
  - `model` -> `gen_ai.response.model`
  - `status` -> `gen_ai.response.status`
  - `created_at` -> `gen_ai.response.created` (epoch float via `.timestamp()`)
  - `usage` -> `gen_ai.usage.input_tokens`, `output_tokens`, `total_tokens`
  - `output_text` -> `bud.inference.response.output_text`

- **`TracedResponseStream`**:
  - `__init__(self, inner, span, context_token, output_fields)` — stores refs, inits counters
  - `__iter__(self)` — yields events from `self._inner`, records TTFT on first event, counts chunks, catches `GeneratorExit`, calls `_finalize()` in `finally`
  - `_finalize(self)` — idempotent; sets chunk count, stream_completed; reads `self._inner.completed_response` for response attrs extraction; ends span; detaches context
  - `__enter__` / `__exit__` / `close()` — context manager
  - `__del__` — safety net

**Acceptance Criteria:**
- [x] `track_responses(client)` instruments `client.responses.create`
- [x] Second call is a no-op (idempotency)
- [x] Non-streaming span has name `"responses"`, correct always-on attributes
- [x] Streaming span has name `"responses.stream"`, returns `TracedResponseStream`
- [x] `TracedResponseStream` records TTFT on first event
- [x] `TracedResponseStream._finalize()` extracts attrs from `completed_response`
- [x] `previous_response_id` mapped to `gen_ai.conversation.id`
- [x] `_is_noop()` fast path returns original result
- [x] Exceptions recorded on span and re-raised
- [x] `ruff check src/bud/observability/_responses_tracker.py` passes

**Depends On:** TASK-9

---

## TASK-11: Register `track_responses` in `observability/__init__.py`

**Description:** Add `track_responses` to the lazy-loaded public API of `bud.observability`.

**Files:**
- `src/bud/observability/__init__.py` (modify)

**Scope:**
- Add entry in `__getattr__()`:
  ```python
  if name == "track_responses":
      from bud.observability._responses_tracker import track_responses
      return track_responses
  ```
- Add `"track_responses"` to `__all__`
- Update module docstring to include: `track_responses() — Instrument client.responses.create()`

**Acceptance Criteria:**
- [x] `from bud.observability import track_responses` works
- [x] `"track_responses" in bud.observability.__all__` is `True`
- [x] Importing `bud.observability` does NOT eagerly import `_responses_tracker`
- [x] Module docstring mentions `track_responses()`
- [x] `ruff check src/bud/observability/__init__.py` passes

**Depends On:** TASK-10

---

## TASK-12: Create `tests/test_observability/test_responses_tracker.py` — tracker unit tests

**Description:** Write unit tests for the internal functions in `_responses_tracker.py`, mirroring `test_inference_tracker.py`.

**Files:**
- `tests/test_observability/test_responses_tracker.py` (create)

**Scope:**

| Test Function | Validates |
|---------------|-----------|
| `test_extract_request_attrs_safe_defaults` | Safe fields captured (model, temperature); NOT input, instructions |
| `test_extract_request_attrs_with_input` | `"input"` in fields -> `bud.inference.request.input` captured as JSON |
| `test_extract_request_attrs_none_fields` | `fields=None` -> empty dict |
| `test_extract_request_attrs_tools_json` | `tools` serialized as JSON string |
| `test_extract_request_attrs_prompt_json` | `prompt` dict serialized as JSON string |
| `test_extract_request_attrs_unmapped` | Unmapped kwarg -> `bud.inference.request.{name}` |
| `test_extract_response_attrs_full` | All safe fields extracted: id, model, status, created_at, usage, output_text |
| `test_extract_response_attrs_none_usage` | Handles `response.usage = None` gracefully |
| `test_extract_response_attrs_none_fields` | `fields=None` -> empty dict |
| `test_extract_response_attrs_created_at_timestamp` | `created_at` datetime converted to epoch float |
| `test_track_responses_idempotency` | Second `track_responses()` call is no-op |
| `test_track_responses_previous_response_id` | `previous_response_id` mapped to `gen_ai.conversation.id` |

**Acceptance Criteria:**
- [x] All tests pass: `pytest tests/test_observability/test_responses_tracker.py -v`
- [x] No external dependencies required (all mocked)
- [x] Uses `unittest.mock.Mock` for `openai.types.responses.Response`
- [x] Tests use the same fixtures/patterns as `test_inference_tracker.py`
- [x] `ruff check tests/test_observability/test_responses_tracker.py` passes

**Depends On:** TASK-11

---

## TASK-13: Create `tests/test_observability/test_responses_integration.py` — integration tests

**Description:** Write integration tests using `InMemorySpanExporter` to verify full span lifecycle for `track_responses()`, mirroring `test_inference_integration.py`.

**Files:**
- `tests/test_observability/test_responses_integration.py` (create)

**Scope:**

| Test Function | Validates |
|---------------|-----------|
| `test_non_streaming_span` | Span name `"responses"`, correct always-on attributes, OK status, response attrs |
| `test_streaming_span` | Span name `"responses.stream"`, TTFT recorded, chunks counted, `stream_completed=True`, response attrs from `completed_response` |
| `test_error_span` | HTTP error -> span status ERROR, exception recorded, re-raised |
| `test_streaming_partial` | Consumer breaks early -> `stream_completed=False`, no ERROR status |
| `test_field_list_mode` | `capture_input=["model"]` -> only model captured, no temperature |
| `test_capture_false` | `capture_input=False, capture_output=False` -> only always-on attributes |
| `test_track_nesting` | `@track` parent span contains `track_responses` child span |

**Acceptance Criteria:**
- [x] All tests pass: `pytest tests/test_observability/test_responses_integration.py -v`
- [x] Uses `InMemorySpanExporter` from `opentelemetry.sdk.trace.export`
- [x] Verifies span names, attribute values, status codes, parent-child relationships
- [x] Mocks `HttpClient` / `Responses.create` to return canned response data
- [x] Streaming test provides mock `ResponseStream` with `completed_response`
- [x] `ruff check tests/test_observability/test_responses_integration.py` passes

**Depends On:** TASK-11

---

## Summary

| Task | Title | Files | Depends On |
|------|-------|-------|------------|
| TASK-1 | Add openai dependency | `pyproject.toml` (modify) | — |
| TASK-2 | Add `async_stream()` to AsyncHttpClient | `_http.py` (modify) | TASK-1 |
| TASK-3 | Create `_response_streaming.py` | `_response_streaming.py` (create) | TASK-2 |
| TASK-4 | Add `Responses` + `AsyncResponses` | `inference.py` (modify) | TASK-3 |
| TASK-5 | Export new resource classes | `resources/__init__.py` (modify) | TASK-4 |
| TASK-6 | Wire `client.responses` | `client.py` (modify) | TASK-5 |
| TASK-7 | Resource unit tests | `test_responses.py` (create) | TASK-6 |
| TASK-8 | Streaming unit tests | `test_response_streaming.py` (create) | TASK-6 |
| TASK-9 | Add Responses API constants | `_genai_attributes.py` (modify) | TASK-6 |
| TASK-10 | Create `_responses_tracker.py` | `_responses_tracker.py` (create) | TASK-9 |
| TASK-11 | Register `track_responses` | `observability/__init__.py` (modify) | TASK-10 |
| TASK-12 | Tracker unit tests | `test_responses_tracker.py` (create) | TASK-11 |
| TASK-13 | Integration tests | `test_responses_integration.py` (create) | TASK-11 |

## Execution Order (Linear)

For sequential execution (e.g., Ralph Wiggum loop), process in this order:

1. TASK-1 → `pyproject.toml`
2. TASK-2 → `src/bud/_http.py`
3. TASK-3 → `src/bud/_response_streaming.py`
4. TASK-4 → `src/bud/resources/inference.py`
5. TASK-5 → `src/bud/resources/__init__.py`
6. TASK-6 → `src/bud/client.py`
7. TASK-7 → `tests/unit/test_responses.py`
8. TASK-8 → `tests/unit/test_response_streaming.py`
9. TASK-9 → `src/bud/observability/_genai_attributes.py`
10. TASK-10 → `src/bud/observability/_responses_tracker.py`
11. TASK-11 → `src/bud/observability/__init__.py`
12. TASK-12 → `tests/test_observability/test_responses_tracker.py`
13. TASK-13 → `tests/test_observability/test_responses_integration.py`

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
