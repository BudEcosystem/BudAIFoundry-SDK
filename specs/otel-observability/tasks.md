# Implementation Tasks: `track_chat_completions()`

## Dependency Graph

```
TASK-1 ──→ TASK-2 ──→ TASK-3
  │                     │
  │                     ├──→ TASK-4 ──→ TASK-7 ──→ TASK-8 ──→ TASK-9
  │                     │              ↗
  │                     ├──→ TASK-5 ──╯
  │                     │              ↗
  │                     └──→ TASK-6 ──╯
  │
  └──→ TASK-10 (after TASK-2..TASK-6)
  └──→ TASK-11 (after TASK-7..TASK-8)
  └──→ TASK-12 (after TASK-9)
```

---

## TASK-1: Create `_genai_attributes.py` — OTel constant definitions

**Description:** Create the GenAI semantic convention constants module. This module contains only string constants and data structures — no logic, no external imports.

**Files:**
- `src/bud/observability/_genai_attributes.py` (create)

**Scope:**
- Define all `GENAI_*` string constants (request, response, usage, content)
- Define all `BUD_INFERENCE_*` string constants
- Define `CHAT_INPUT_ATTR_MAP: dict[str, str]` — maps kwarg names to OTel attribute keys
- Define `CHAT_SAFE_INPUT_FIELDS: frozenset[str]` — safe default input fields (no PII)
- Define `CHAT_SAFE_OUTPUT_FIELDS: frozenset[str]` — safe default output fields (no PII)

**Acceptance Criteria:**
- [x] Module imports without error: `python -c "from bud.observability._genai_attributes import *"`
- [x] `CHAT_SAFE_INPUT_FIELDS` contains: `model`, `temperature`, `top_p`, `max_tokens`, `stop`, `presence_penalty`, `frequency_penalty`, `stream`, `tool_choice`
- [x] `CHAT_SAFE_INPUT_FIELDS` does NOT contain: `messages`, `tools`, `user`
- [x] `CHAT_SAFE_OUTPUT_FIELDS` contains: `id`, `model`, `created`, `usage`, `system_fingerprint`, `finish_reason`
- [x] `CHAT_SAFE_OUTPUT_FIELDS` does NOT contain: `content`
- [x] `CHAT_INPUT_ATTR_MAP["messages"]` == `"gen_ai.content.prompt"`
- [x] All constant values follow OTel GenAI semantic conventions
- [x] `ruff check` passes

**Depends On:** None

---

## TASK-2: Implement field resolution — `_resolve_fields()`

**Description:** Implement the `FieldCapture` type alias and `_resolve_fields()` function that converts user-facing capture configuration into an internal field set.

**Files:**
- `src/bud/observability/_inference_tracker.py` (create — this task creates the file with the first function)

**Scope:**
- Define `FieldCapture = bool | list[str]` type alias
- Implement `_resolve_fields(capture: FieldCapture, safe_defaults: frozenset[str]) -> frozenset[str] | None`
- `True` → returns `safe_defaults`
- `False` → returns `None`
- `list[str]` → returns `frozenset(list)`

**Acceptance Criteria:**
- [x] `_resolve_fields(True, CHAT_SAFE_INPUT_FIELDS)` returns `CHAT_SAFE_INPUT_FIELDS`
- [x] `_resolve_fields(False, CHAT_SAFE_INPUT_FIELDS)` returns `None`
- [x] `_resolve_fields(["model", "messages"], CHAT_SAFE_INPUT_FIELDS)` returns `frozenset({"model", "messages"})`
- [x] `ruff check` passes
- [x] Type annotations are correct

**Depends On:** TASK-1

---

## TASK-3: Implement request attribute extraction — `_extract_chat_request_attrs()`

**Description:** Implement the function that converts `create()` keyword arguments into OTel span attributes, respecting the resolved field set.

**Files:**
- `src/bud/observability/_inference_tracker.py` (modify — add function)

**Scope:**
- Implement `_extract_chat_request_attrs(kwargs: dict[str, Any], fields: frozenset[str] | None) -> dict[str, Any]`
- If `fields is None`: return empty dict
- For each kwarg name in `fields ∩ kwargs.keys()`:
  - Look up attribute key in `CHAT_INPUT_ATTR_MAP`
  - `"messages"` / `"tools"` → `json.dumps(value)` truncated via `_safe_repr()`
  - `"stop"` when list → `json.dumps(value)`
  - Scalar values → stored directly
  - No mapping found → `bud.inference.request.{name}`
- Import `_safe_repr` from `_track.py`

**Acceptance Criteria:**
- [x] `_extract_chat_request_attrs({"model": "gpt-4", "temperature": 0.7}, safe_fields)` returns `{"gen_ai.request.model": "gpt-4", "gen_ai.request.temperature": 0.7}`
- [x] `_extract_chat_request_attrs({"model": "gpt-4", "messages": [...]}, frozenset({"model", "messages"}))` includes `"gen_ai.content.prompt"` with JSON-serialized messages
- [x] `_extract_chat_request_attrs({"model": "gpt-4"}, None)` returns `{}`
- [x] Unmapped kwargs produce `bud.inference.request.{name}` keys
- [x] String values truncated to 1000 chars
- [x] `ruff check` passes

**Depends On:** TASK-1, TASK-2

---

## TASK-4: Implement response attribute extraction — `_extract_chat_response_attrs()`

**Description:** Implement the function that extracts span attributes from a `ChatCompletion` response object.

**Files:**
- `src/bud/observability/_inference_tracker.py` (modify — add function)

**Scope:**
- Implement `_extract_chat_response_attrs(response: ChatCompletion, fields: frozenset[str] | None) -> dict[str, Any]`
- If `fields is None`: return empty dict
- Field mapping:
  - `"id"` → `gen_ai.response.id`
  - `"model"` → `gen_ai.response.model`
  - `"created"` → `gen_ai.response.created`
  - `"system_fingerprint"` → `gen_ai.response.system_fingerprint` (only if non-None)
  - `"usage"` → `gen_ai.usage.input_tokens` + `gen_ai.usage.output_tokens`
  - `"finish_reason"` → `gen_ai.response.finish_reasons = [reason]`
  - `"content"` → `gen_ai.content.completion` (PII — truncated)

**Acceptance Criteria:**
- [x] Extracts `id`, `model`, `created` correctly from a `ChatCompletion` mock
- [x] Usage fields mapped from `prompt_tokens` → `input_tokens`, `completion_tokens` → `output_tokens`
- [x] `finish_reason` wrapped in a list: `["stop"]`
- [x] `system_fingerprint` skipped when `None`
- [x] `content` only extracted when `"content"` is in the field set
- [x] `_extract_chat_response_attrs(response, None)` returns `{}`
- [x] `ruff check` passes

**Depends On:** TASK-1, TASK-2, TASK-3

---

## TASK-5: Implement stream aggregation — `_aggregate_stream_response()`

**Description:** Implement the function that aggregates accumulated `ChatCompletionChunk` objects into span attributes after stream iteration completes.

**Files:**
- `src/bud/observability/_inference_tracker.py` (modify — add function)

**Scope:**
- Implement `_aggregate_stream_response(chunks: list[ChatCompletionChunk], fields: frozenset[str] | None) -> dict[str, Any]`
- Extraction logic:
  - `"id"`: first chunk with an `id`
  - `"model"`: first chunk with a `model`
  - `"system_fingerprint"`: first chunk with non-None `system_fingerprint`
  - `"finish_reason"`: chunk with non-None `choices[0].finish_reason`
  - `"usage"`: reverse search — `getattr(chunk, "usage", None)` on `reversed(chunks)`
  - `"content"`: join all `delta.content` strings AND all `delta.reasoning_content` strings, truncate
- Only includes fields present in the `fields` set

**Acceptance Criteria:**
- [x] Joins `delta.content` across 5 chunks correctly
- [x] Joins `delta.reasoning_content` for reasoning models (o1, etc.)
- [x] Finds `usage` from last chunk when provider sends usage in final chunk
- [x] Finds `finish_reason` from the chunk that has it
- [x] Returns empty dict when `fields is None`
- [x] Handles empty chunks list without error
- [x] `ruff check` passes

**Depends On:** TASK-1, TASK-2, TASK-3

---

## TASK-6: Implement `TracedChatStream` — streaming wrapper class

**Description:** Implement the `TracedChatStream` class that wraps `Stream[ChatCompletionChunk]` with OTel span lifecycle management.

**Files:**
- `src/bud/observability/_inference_tracker.py` (modify — add class)

**Scope:**
- `__init__(self, inner, span, context_token, output_fields)`
- `__iter__(self)` — yields chunks, records TTFT on first chunk, accumulates chunks, handles `GeneratorExit`, calls `_finalize()` in `finally`
- `_finalize(self)` — guarded by `_finalized` flag; sets chunk count, stream_completed, aggregates response, ends span, detaches context
- `__enter__` / `__exit__` / `close()` — context manager support
- `__del__` — safety net calling `_finalize()` with warning log

**Acceptance Criteria:**
- [x] TTFT recorded as `bud.inference.ttft_ms` on first chunk
- [x] `bud.inference.chunks` reflects total chunks yielded
- [x] `bud.inference.stream_completed` is `True` for full iteration, `False` for partial
- [x] `_finalize()` is idempotent (second call is no-op)
- [x] `__del__` calls `_finalize()` with `logger.warning()` if not already finalized
- [x] `GeneratorExit` does not set ERROR status
- [x] Mid-stream exception records exception on span and re-raises
- [x] `close()` delegates to `self._inner.close()`
- [x] `ruff check` passes

**Depends On:** TASK-1, TASK-2, TASK-3, TASK-5

---

## TASK-7: Implement `track_chat_completions()` — public API

**Description:** Implement the main public function that monkey-patches `client.chat.completions.create()` with the OTel-instrumented wrapper.

**Files:**
- `src/bud/observability/_inference_tracker.py` (modify — add function)

**Scope:**
- 5-step flow:
  1. Idempotency guard via `_bud_tracked` attribute
  2. Save reference to `original_create`
  3. Resolve field sets via `_resolve_fields()` (once at patch time)
  4. Define `traced_create(**kwargs)` wrapper:
     - `_is_noop()` fast path
     - Determine streaming vs non-streaming from `kwargs.get("stream", False)`
     - Create span via `create_traced_span()`
     - Set always-on attributes: `gen_ai.system`, `bud.inference.operation`, `bud.inference.stream`
     - Extract and set request attributes
     - Call `original_create(**kwargs)`
     - Non-streaming: extract response attrs, set OK, end span, detach context, return
     - Streaming: return `TracedChatStream(result, span, token, output_fields)`
  5. Patch: `client.chat.completions.create = traced_create`, set `_bud_tracked = True`, return client

**Acceptance Criteria:**
- [x] Returns the same client object
- [x] Second call is a no-op (idempotency)
- [x] `_is_noop()` fast path returns original result with no span
- [x] Non-streaming: span has correct name (`"chat"`), attributes, OK status
- [x] Streaming: span has correct name (`"chat.stream"`), returns `TracedChatStream`
- [x] Exceptions from `original_create()` are recorded on span and re-raised
- [x] `ruff check` passes

**Depends On:** TASK-1, TASK-2, TASK-3, TASK-4, TASK-5, TASK-6

---

## TASK-8: Update `__init__.py` — lazy import and `__all__`

**Description:** Add `track_chat_completions` to the public API surface of `bud.observability`.

**Files:**
- `src/bud/observability/__init__.py` (modify)

**Scope:**
- Add lazy import in `__getattr__()`:
  ```python
  if name == "track_chat_completions":
      from bud.observability._inference_tracker import track_chat_completions
      return track_chat_completions
  ```
- Add `"track_chat_completions"` to `__all__`
- Update module docstring to include: `track_chat_completions() — Instrument client.chat.completions.create()`

**Acceptance Criteria:**
- [x] `from bud.observability import track_chat_completions` works
- [x] `"track_chat_completions" in bud.observability.__all__` is `True`
- [x] Importing `bud.observability` does NOT eagerly import `_inference_tracker`
- [x] `ruff check` passes

**Depends On:** TASK-7

---

## TASK-9: Create example script

**Description:** Create a demonstration script showing all usage patterns for `track_chat_completions()`.

**Files:**
- `examples/observability/track_inference.py` (create)

**Scope:**
- Example 1: Basic non-streaming traced call with safe defaults
- Example 2: Streaming traced call showing TTFT
- Example 3: Error handling (bad model name → exception, span records error)
- Example 4: PII opt-in via `capture_input=["model", "messages"]`
- Example 5: Nesting with `@track` decorator (parent-child spans)
- Include `configure()` setup and `shutdown()` cleanup
- Include inline comments explaining what each section demonstrates

**Acceptance Criteria:**
- [x] Script is syntactically valid: `python -c "import ast; ast.parse(open('...').read())"`
- [x] All 5 usage patterns demonstrated
- [x] `configure()` called at top, `shutdown()` called at end
- [x] `ruff check` passes
- [x] Comments explain expected span output for each example

**Depends On:** TASK-8

---

## TASK-10: Write unit tests

**Description:** Write unit tests for all internal functions using mocked dependencies.

**Files:**
- `tests/observability/test_inference_tracker.py` (create)

**Scope:**

| Test Function | Validates |
|---------------|-----------|
| `test_resolve_fields_true` | `True` returns safe defaults frozenset |
| `test_resolve_fields_false` | `False` returns `None` |
| `test_resolve_fields_list` | `list[str]` returns `frozenset` |
| `test_extract_request_attrs_safe_defaults` | Captures model, temperature; NOT messages |
| `test_extract_request_attrs_with_messages` | `"messages"` in fields → `gen_ai.content.prompt` captured |
| `test_extract_request_attrs_none_fields` | `fields=None` → empty dict |
| `test_extract_request_attrs_unmapped` | Unmapped kwarg → `bud.inference.request.{name}` |
| `test_extract_request_attrs_stop_list` | `stop` as list → JSON serialized |
| `test_extract_response_attrs_full` | All safe fields extracted correctly |
| `test_extract_response_attrs_content` | `"content"` in fields → completion captured |
| `test_extract_response_attrs_none_usage` | Handles `response.usage = None` gracefully |
| `test_extract_response_attrs_none_fields` | `fields=None` → empty dict |
| `test_aggregate_stream_basic` | Joins content, finds finish_reason |
| `test_aggregate_stream_reasoning` | Joins `reasoning_content` for reasoning models |
| `test_aggregate_stream_usage_last_chunk` | Finds usage from final chunk |
| `test_aggregate_stream_empty` | Empty chunks list → empty dict |
| `test_idempotency` | Second `track_chat_completions()` is no-op |

**Acceptance Criteria:**
- [x] All tests pass: `pytest tests/test_observability/test_inference_tracker.py` (21 passed)
- [x] No external dependencies required (all mocked)
- [x] Tests use `unittest.mock.Mock` for `ChatCompletion`, `ChatCompletionChunk`
- [x] `ruff check` passes

**Depends On:** TASK-2, TASK-3, TASK-4, TASK-5, TASK-6

---

## TASK-11: Write integration tests

**Description:** Write integration tests using `InMemorySpanExporter` to verify full span lifecycle.

**Files:**
- `tests/observability/test_inference_integration.py` (create)

**Scope:**

| Test Function | Validates |
|---------------|-----------|
| `test_non_streaming_span` | Span created with name `"chat"`, correct attributes, OK status |
| `test_streaming_span` | Span name `"chat.stream"`, TTFT recorded, chunks counted, `stream_completed=True` |
| `test_streaming_partial` | Consumer breaks early → `stream_completed=False`, no ERROR status |
| `test_error_span` | HTTP error → span status ERROR, exception recorded, re-raised |
| `test_field_list_mode` | `capture_input=["model"]` → only model captured, no temperature |
| `test_capture_false` | `capture_input=False, capture_output=False` → no input/output attributes, only always-on |
| `test_track_nesting` | `@track` wrapping a function that calls traced `create()` → parent-child span relationship |

**Acceptance Criteria:**
- [x] All tests pass: `pytest tests/test_observability/test_inference_integration.py` (7 passed)
- [x] Uses `InMemorySpanExporter` from `opentelemetry.sdk.trace.export.in_memory_span_exporter`
- [x] Verifies span names, attribute values, status codes, parent-child relationships
- [x] Mocks `HttpClient` to return canned `ChatCompletion` / `ChatCompletionChunk` data
- [x] `ruff check` passes

**Depends On:** TASK-7, TASK-8

---

## TASK-12: Manual ClickHouse validation

**Description:** Run the example script against a live Bud endpoint and verify spans appear in ClickHouse.

**Files:**
- None (manual process)

**Scope:**
1. Configure observability: `configure(api_key="...", collector_endpoint="...")`
2. Run `examples/observability/track_inference.py`
3. Query ClickHouse:
   ```sql
   SELECT
       SpanName,
       SpanAttributes['gen_ai.system'] AS system,
       SpanAttributes['gen_ai.request.model'] AS model,
       SpanAttributes['gen_ai.usage.input_tokens'] AS input_tokens,
       SpanAttributes['gen_ai.usage.output_tokens'] AS output_tokens,
       SpanAttributes['bud.inference.ttft_ms'] AS ttft_ms,
       SpanAttributes['bud.inference.stream_completed'] AS stream_completed,
       StatusCode
   FROM default_v8.otel_traces
   WHERE SpanAttributes['gen_ai.system'] = 'bud'
   ORDER BY Timestamp DESC
   LIMIT 10;
   ```
4. Verify:
   - Non-streaming span: `SpanName="chat"`, `StatusCode=OK`, usage tokens present
   - Streaming span: `SpanName="chat.stream"`, `ttft_ms > 0`, `stream_completed="true"`
   - Error span: `StatusCode=ERROR`

**Acceptance Criteria:**
- [ ] Non-streaming spans visible in ClickHouse with correct attributes (manual — requires live Bud endpoint)
- [ ] Streaming spans have TTFT and chunk count (manual — requires live Bud endpoint)
- [ ] Error spans have ERROR status and recorded exception (manual — requires live Bud endpoint)
- [ ] No PII in spans when using safe defaults (manual — requires live Bud endpoint)

**Depends On:** TASK-9

---

## Summary

| Task | Title | Files | Depends On |
|------|-------|-------|------------|
| TASK-1 | Create `_genai_attributes.py` | `_genai_attributes.py` (create) | — |
| TASK-2 | Implement field resolution | `_inference_tracker.py` (create) | TASK-1 |
| TASK-3 | Implement request attribute extraction | `_inference_tracker.py` (modify) | TASK-1, TASK-2 |
| TASK-4 | Implement response attribute extraction | `_inference_tracker.py` (modify) | TASK-1, TASK-2, TASK-3 |
| TASK-5 | Implement stream aggregation | `_inference_tracker.py` (modify) | TASK-1, TASK-2, TASK-3 |
| TASK-6 | Implement `TracedChatStream` | `_inference_tracker.py` (modify) | TASK-1..TASK-3, TASK-5 |
| TASK-7 | Implement `track_chat_completions()` | `_inference_tracker.py` (modify) | TASK-1..TASK-6 |
| TASK-8 | Update `__init__.py` | `__init__.py` (modify) | TASK-7 |
| TASK-9 | Create example script | `track_inference.py` (create) | TASK-8 |
| TASK-10 | Write unit tests | `test_inference_tracker.py` (create) | TASK-2..TASK-6 |
| TASK-11 | Write integration tests | `test_inference_integration.py` (create) | TASK-7, TASK-8 |
| TASK-12 | Manual ClickHouse validation | *(manual)* | TASK-9 |
