# Implementation Plan: `track_chat_completions()`

## 1. Overview

`track_chat_completions()` adds OpenTelemetry-based observability to the BudAIFoundry SDK's chat completions API. It monkey-patches `client.chat.completions.create()` with an instrumented wrapper that:

- Creates OTel spans for every chat completion call (streaming and non-streaming)
- Records request parameters, response metadata, and token usage as span attributes
- Follows [OpenTelemetry GenAI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- Provides configurable field capture with PII-safe defaults
- Measures Time-To-First-Token (TTFT) for streaming responses
- Integrates with the existing `@track` decorator via OTel context propagation

The goal is zero-effort observability: one function call instruments all chat completions with production-safe defaults, while giving advanced users full control over what is captured.

---

## 2. Public API

### Function Signature

```python
def track_chat_completions(
    client: BudClient,
    *,
    capture_input: bool | list[str] = True,
    capture_output: bool | list[str] = True,
    span_name: str = "chat",
) -> BudClient:
```

### Usage Examples

**Example 1: Safe defaults (no PII captured)**
```python
from bud import BudClient
from bud.observability import track_chat_completions

client = BudClient(api_key="bud_xxxx")
track_chat_completions(client)

response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello!"}],
)
# Span attributes: model, temperature, usage, finish_reason, id, etc.
# Messages and content are NOT captured.
```

**Example 2: Opt into PII capture**
```python
track_chat_completions(
    client,
    capture_input=["model", "messages"],      # "messages" opts into prompt capture
    capture_output=["usage", "content"],       # "content" opts into completion capture
)
```

**Example 3: Capture nothing (span-only, no attributes)**
```python
track_chat_completions(client, capture_input=False, capture_output=False)
```

---

## 3. Three-Mode Field Capture

The `capture_input` and `capture_output` parameters accept `True | False | list[str]`:

| Value | Behavior | Resulting Field Set |
|-------|----------|-------------------|
| `True` | Safe defaults — no PII fields | `CHAT_SAFE_INPUT_FIELDS` or `CHAT_SAFE_OUTPUT_FIELDS` |
| `False` | Capture nothing | `None` |
| `list[str]` | Capture exactly these fields | `frozenset(list)` |

**PII rule:** The fields `"messages"` (input) and `"content"` (output) are never included in safe defaults. Users must explicitly list them to opt in.

**Type alias:**
```python
FieldCapture = bool | list[str]
```

**Resolution function:**
```python
def _resolve_fields(
    capture: FieldCapture, safe_defaults: frozenset[str]
) -> frozenset[str] | None:
    if capture is True:
        return safe_defaults
    if capture is False:
        return None
    return frozenset(capture)
```

Field resolution happens once at patch time, not per call.

---

## 4. File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/bud/observability/_genai_attributes.py` | **Create** | OTel GenAI semantic convention constants, safe field sets, attribute mapping |
| `src/bud/observability/_inference_tracker.py` | **Create** | Core implementation: field resolution, attribute extraction, `TracedChatStream`, `track_chat_completions()` |
| `src/bud/observability/__init__.py` | **Modify** | Add lazy import for `track_chat_completions` in `__getattr__`, add to `__all__`, update module docstring |
| `examples/observability/track_inference.py` | **Create** | Example script demonstrating all usage patterns |

---

## 5. Module Structure

### `_genai_attributes.py`

Contains only constants — no logic, no imports beyond builtins.

```
_genai_attributes.py
├── GenAI request constants (GENAI_REQUEST_MODEL, GENAI_REQUEST_TEMPERATURE, ...)
├── GenAI response constants (GENAI_RESPONSE_ID, GENAI_RESPONSE_MODEL, ...)
├── GenAI usage constants (GENAI_USAGE_INPUT_TOKENS, GENAI_USAGE_OUTPUT_TOKENS)
├── GenAI content constants (GENAI_CONTENT_PROMPT, GENAI_CONTENT_COMPLETION)
├── Bud-specific constants (BUD_INFERENCE_STREAM, BUD_INFERENCE_TTFT_MS, ...)
├── CHAT_INPUT_ATTR_MAP: dict[str, str]   — kwarg name → OTel attribute key
├── CHAT_SAFE_INPUT_FIELDS: frozenset[str] — safe default input fields
└── CHAT_SAFE_OUTPUT_FIELDS: frozenset[str] — safe default output fields
```

### `_inference_tracker.py`

Contains all logic. Internal functions are prefixed with `_`.

```
_inference_tracker.py
├── FieldCapture          — type alias: bool | list[str]
├── _resolve_fields()     — resolve capture config → frozenset | None
├── _extract_chat_request_attrs()  — kwargs dict → span attribute dict
├── _extract_chat_response_attrs() — ChatCompletion → span attribute dict
├── _aggregate_stream_response()   — list[ChatCompletionChunk] → span attribute dict
├── TracedChatStream      — streaming wrapper class with span lifecycle
└── track_chat_completions()       — public API, monkey-patches client
```

---

## 6. Key Functions

### `_resolve_fields(capture, safe_defaults) -> frozenset[str] | None`

- **Input:** `capture: FieldCapture`, `safe_defaults: frozenset[str]`
- **Output:** `frozenset[str]` of fields to capture, or `None` if capture is disabled
- **Called:** Once at patch time (not per request)

### `_extract_chat_request_attrs(kwargs, fields) -> dict[str, Any]`

- **Input:** `kwargs: dict[str, Any]` (the `**kwargs` passed to `create()`), `fields: frozenset[str] | None`
- **Output:** `dict[str, Any]` mapping OTel attribute keys to values
- **Logic:**
  - If `fields is None`: return `{}`
  - For each kwarg name in `fields ∩ kwargs.keys()`:
    - Look up OTel key in `CHAT_INPUT_ATTR_MAP`
    - `"messages"` / `"tools"` → `json.dumps(value)` truncated via `_safe_repr()`
    - `"stop"` when list → `json.dumps(value)`
    - Scalar values → stored directly
    - No mapping found → `bud.inference.request.{name}`
- **Always-on attributes** (`gen_ai.system`, `bud.inference.operation`) are set on the span directly by the caller, not by this function.

### `_extract_chat_response_attrs(response, fields) -> dict[str, Any]`

- **Input:** `response: ChatCompletion`, `fields: frozenset[str] | None`
- **Output:** `dict[str, Any]` mapping OTel attribute keys to values
- **Mapping:**
  - `"id"` → `gen_ai.response.id` (from `response.id`)
  - `"model"` → `gen_ai.response.model` (from `response.model`)
  - `"created"` → `gen_ai.response.created` (from `response.created`)
  - `"system_fingerprint"` → `gen_ai.response.system_fingerprint` (only if non-None)
  - `"usage"` → `gen_ai.usage.input_tokens` + `gen_ai.usage.output_tokens` (from `response.usage.prompt_tokens` / `completion_tokens`)
  - `"finish_reason"` → `gen_ai.response.finish_reasons = [reason]` (from `response.choices[0].finish_reason`)
  - `"content"` → `gen_ai.content.completion` (PII: from `response.choices[0].message.content`, truncated)

### `_aggregate_stream_response(chunks, fields) -> dict[str, Any]`

- **Input:** `chunks: list[ChatCompletionChunk]`, `fields: frozenset[str] | None`
- **Output:** `dict[str, Any]` mapping OTel attribute keys to values
- **Logic:**
  - `"id"`: first chunk with an `id`
  - `"model"`: first chunk with a `model`
  - `"system_fingerprint"`: first chunk with non-None `system_fingerprint`
  - `"finish_reason"`: chunk with non-None `finish_reason` in `choices[0]`
  - `"usage"`: search in reverse order via `reversed(chunks)` — some providers send usage in the final chunk. Access via `getattr(chunk, "usage", None)`
  - `"content"`: join all `delta.content` strings AND all `delta.reasoning_content` strings (for reasoning models like o1), then truncate via `_safe_repr()`

---

## 7. `TracedChatStream` Class Design

`TracedChatStream` is a drop-in wrapper for `Stream[ChatCompletionChunk]` that manages span lifecycle across the streaming iteration.

```python
class TracedChatStream:
    def __init__(self, inner, span, context_token, output_fields):
        self._inner = inner                          # Original Stream object
        self._span = span                            # OTel Span (manually managed)
        self._context_token = context_token          # OTel context token for detach
        self._output_fields = output_fields          # frozenset | None
        self._chunk_count = 0                        # int
        self._accumulated: list[ChatCompletionChunk] = []
        self._completed = False                      # True if stream fully consumed
        self._finalized = False                      # Guard against double-end
        self._start_time = time.monotonic()
        self._first_chunk_time: float | None = None

    def __iter__(self):
        try:
            for chunk in self._inner:
                if self._first_chunk_time is None:
                    self._first_chunk_time = time.monotonic()
                    self._span.set_attribute(
                        BUD_INFERENCE_TTFT_MS,
                        (self._first_chunk_time - self._start_time) * 1000,
                    )
                self._chunk_count += 1
                self._accumulated.append(chunk)
                yield chunk
            self._completed = True
        except GeneratorExit:
            pass  # Consumer stopped early — partial completion
        except Exception as exc:
            _record_exception(self._span, exc)
            raise
        finally:
            self._finalize()

    def _finalize(self):
        if self._finalized:
            return
        self._finalized = True

        self._span.set_attribute(BUD_INFERENCE_CHUNKS, self._chunk_count)
        self._span.set_attribute(BUD_INFERENCE_STREAM_COMPLETED, self._completed)

        if self._accumulated:
            try:
                for k, v in _aggregate_stream_response(
                    self._accumulated, self._output_fields
                ).items():
                    self._span.set_attribute(k, v)
            except Exception:
                logger.debug("Failed to aggregate stream response", exc_info=True)

        if self._completed:
            _set_ok_status(self._span)

        self._span.end()
        if self._context_token is not None:
            context.detach(self._context_token)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        self._inner.close()

    def __del__(self):
        if not self._finalized:
            logger.warning("TracedChatStream was garbage-collected without iteration")
            self._finalize()
```

**Key properties:**
- TTFT measured via `time.monotonic()` difference on first chunk
- All chunks accumulated for post-stream aggregation (in `_finalize()`)
- `_finalized` guard prevents double-ending the span
- `__del__` safety net ensures the span is ended even if the stream is never iterated
- `close()` delegates to the inner stream (releases HTTP resources)
- `GeneratorExit` is caught and treated as partial completion (not an error)

---

## 8. `track_chat_completions()` — 5-Step Monkey-Patch Flow

```python
def track_chat_completions(client, *, capture_input=True, capture_output=True, span_name="chat"):
    # Step 1: Idempotency guard
    if getattr(client.chat.completions, '_bud_tracked', False):
        return client

    # Step 2: Save original method reference
    original_create = client.chat.completions.create

    # Step 3: Resolve field sets (once at patch time)
    input_fields = _resolve_fields(capture_input, CHAT_SAFE_INPUT_FIELDS)
    output_fields = _resolve_fields(capture_output, CHAT_SAFE_OUTPUT_FIELDS)

    # Step 4: Define wrapper
    def traced_create(**kwargs):
        # Fast path: skip if observability not configured
        if _is_noop():
            return original_create(**kwargs)

        is_streaming = kwargs.get("stream", False)
        effective_span_name = f"{span_name}.stream" if is_streaming else span_name

        # Create span with manual lifecycle management
        span, token = create_traced_span(effective_span_name, get_tracer("bud.inference"))

        # Set always-on attributes
        span.set_attribute(GENAI_SYSTEM, "bud")
        span.set_attribute(BUD_INFERENCE_OPERATION, "chat")
        span.set_attribute(BUD_INFERENCE_STREAM, is_streaming)

        # Extract and set request attributes
        for k, v in _extract_chat_request_attrs(kwargs, input_fields).items():
            span.set_attribute(k, v)

        # Call original
        try:
            result = original_create(**kwargs)
        except Exception as exc:
            _record_exception(span, exc)
            span.end()
            context.detach(token)
            raise

        # Handle response
        if is_streaming:
            return TracedChatStream(result, span, token, output_fields)
        else:
            try:
                for k, v in _extract_chat_response_attrs(result, output_fields).items():
                    span.set_attribute(k, v)
            except Exception:
                logger.debug("Failed to extract response attributes", exc_info=True)
            _set_ok_status(span)
            span.end()
            context.detach(token)
            return result

    # Step 5: Monkey-patch
    client.chat.completions.create = traced_create
    client.chat.completions._bud_tracked = True
    return client
```

---

## 9. Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Patching mechanism** | Monkey-patch instance method | Same object identity preserved; `isinstance()` checks still pass; simplest approach |
| **PII handling** | Safe defaults exclude `messages`/`content`; user opts in via field list | No separate `capture_pii` flag needed — `["messages"]` is explicit enough |
| **Span lifecycle (non-streaming)** | `create_traced_span()` + manual `span.end()` / `context.detach()` | Consistent with streaming path; avoids nesting context managers |
| **Span lifecycle (streaming)** | Span created in wrapper, ended in `TracedChatStream._finalize()` | Span must outlive the `create()` call — it covers the entire iteration |
| **Idempotency** | `_bud_tracked` flag on `ChatCompletions` instance | Prevents double-patching; checked once at patch time; lightweight |
| **Field capture** | `True \| False \| list[str]` union type | Three modes cover all use cases; consistent for input and output |
| **Field resolution timing** | At patch time, not per call | Avoids repeated work; field sets are immutable (`frozenset`) |
| **Context propagation** | Manual `context.attach()` / `context.detach()` | Works with `@track` decorator nesting via standard OTel context |
| **Attribute fallback** | Unmapped fields → `bud.inference.request.{name}` | Future-proof; new kwargs are captured without code changes |
| **Stream accumulation** | All chunks stored in list | Required for post-stream aggregation (usage, content, finish_reason) |

---

## 10. Error Handling Matrix

| Scenario | Span Status | Exception Recorded | Re-raised | Notes |
|----------|------------|-------------------|-----------|-------|
| HTTP 401 / 404 / 422 / 429 / 5xx | ERROR | Yes | Yes | SDK raises `APIError` subclass |
| `ConnectionError` / `TimeoutError` | ERROR | Yes | Yes | Network-level failure |
| Streaming: `GeneratorExit` (consumer stops early) | OK (partial) | No | No | `stream_completed=False` |
| Streaming: exception mid-stream | ERROR | Yes | Yes | `stream_completed=False` |
| Streaming: normal completion | OK | No | No | `stream_completed=True` |
| Attribute extraction failure | (no effect on status) | No | No | `logger.debug()` only |
| `_aggregate_stream_response()` failure | (no effect on status) | No | No | `logger.debug()` only |

**Core principle:** Tracing is transparent. Exceptions from the user's API call are always re-raised. Tracing failures never propagate to the user.

---

## 11. Performance Safeguards

1. **`_is_noop()` fast path** — When observability is not configured, `traced_create()` calls `original_create()` directly with zero OTel overhead. This check is a single attribute lookup on the global state object.

2. **No deep copies** — Request kwargs and response objects are read by reference. No serialization or copying unless a field is explicitly captured.

3. **Streaming per-chunk cost** — One `list.append()` + one `int += 1` per chunk. All aggregation happens once in `_finalize()` after the stream ends.

4. **Lazy imports** — `opentelemetry.context` and `opentelemetry.trace` are imported at call time, not module load time. The module can be imported without OTel installed.

5. **String truncation** — All string attributes are truncated to 1000 characters via `_safe_repr()`. Prevents large message payloads from bloating spans.

6. **No message serialization by default** — `json.dumps(messages)` only runs when `"messages"` is explicitly in the input field list. Safe defaults never trigger serialization.

---

## 12. Edge Cases

| # | Edge Case | Handling |
|---|-----------|----------|
| 1 | **Double-patching** | `_bud_tracked` flag on `ChatCompletions` — second call is a no-op, returns client immediately |
| 2 | **OTel not installed** | `_is_noop()` returns `True` — original method called directly, no span created |
| 3 | **Stream never iterated** | `__del__` safety net calls `_finalize()` with warning log — span is ended, context detached |
| 4 | **Reasoning models** (e.g., o1) | `_aggregate_stream_response()` joins both `delta.content` and `delta.reasoning_content` |
| 5 | **Tool call streaming** | `delta.tool_calls` accumulated when `"content"` is in output fields |
| 6 | **Attribute extraction failure** | `try/except` → `logger.debug()` — never affects user's API call |
| 7 | **`@track` decorator nesting** | Works automatically via OTel context propagation — `track_chat_completions` span becomes a child of the `@track` span |
| 8 | **Concurrent threads** | Thread-safe — each call creates its own span + context token, no shared mutable state |
| 9 | **`_finalize()` called twice** | `_finalized` boolean guard prevents double `span.end()` |

---

## 13. Reusable Code from Existing Codebase

| Utility | Location | Import Path |
|---------|----------|-------------|
| `_is_noop()` | `_track.py:51` | `from bud.observability._track import _is_noop` |
| `_safe_repr()` | `_track.py:40` | `from bud.observability._track import _safe_repr` |
| `_record_exception()` | `_track.py:156` | `from bud.observability._track import _record_exception` |
| `_set_ok_status()` | `_track.py:167` | `from bud.observability._track import _set_ok_status` |
| `_MAX_ATTR_LENGTH` | `_track.py:31` | `from bud.observability._track import _MAX_ATTR_LENGTH` |
| `create_traced_span()` | `__init__.py:153` | `from bud.observability import create_traced_span` |
| `get_tracer()` | `__init__.py:103` | `from bud.observability import get_tracer` |

The existing `TracedStream` class in `_stream_wrapper.py` served as the design template for `TracedChatStream`, but `TracedChatStream` adds chunk accumulation, field-aware aggregation, finalize guard, and `__del__` safety net.

---

## 14. Verification Plan

### Unit Tests

| Test | Validates |
|------|-----------|
| `test_resolve_fields_true` | `True` → returns safe defaults frozenset |
| `test_resolve_fields_false` | `False` → returns `None` |
| `test_resolve_fields_list` | `["model", "messages"]` → returns `frozenset({"model", "messages"})` |
| `test_extract_request_attrs_safe_defaults` | Captures model, temperature, etc. but NOT messages |
| `test_extract_request_attrs_with_messages` | When `"messages"` in fields, captures serialized messages |
| `test_extract_request_attrs_none` | `fields=None` → empty dict |
| `test_extract_response_attrs_full` | Extracts id, model, usage, finish_reason |
| `test_extract_response_attrs_content` | When `"content"` in fields, captures completion text |
| `test_aggregate_stream_basic` | Joins content from chunks, extracts finish_reason |
| `test_aggregate_stream_reasoning` | Joins both `content` and `reasoning_content` |
| `test_aggregate_stream_usage` | Finds usage from last chunk (reverse search) |
| `test_idempotency` | Second `track_chat_completions()` call is no-op |

### Integration Tests (InMemorySpanExporter)

| Test | Validates |
|------|-----------|
| `test_non_streaming_span` | Span created with correct name, attributes, OK status |
| `test_streaming_span` | Span name `"chat.stream"`, TTFT recorded, chunks counted, stream_completed |
| `test_error_span` | HTTP error → span status ERROR, exception recorded, re-raised |
| `test_field_list_mode` | `capture_input=["model"]` → only model captured |
| `test_capture_false` | `capture_input=False` → no input attributes |
| `test_track_nesting` | `@track` + `track_chat_completions` → parent-child span relationship |

### Manual ClickHouse Validation

Run the example script against a live endpoint and verify:
```sql
SELECT
    SpanName, SpanAttributes, StatusCode
FROM default_v8.otel_traces
WHERE SpanAttributes['gen_ai.system'] = 'bud'
ORDER BY Timestamp DESC
LIMIT 10;
```

### Example Script

`examples/observability/track_inference.py` demonstrates:
1. Basic non-streaming traced call
2. Streaming traced call with TTFT
3. Error handling (bad model name)
4. PII opt-in via `capture_input=["model", "messages"]`
5. Nesting with `@track` decorator
