# Technical Specification: `track_chat_completions()`

## 1. API Contract

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

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `client` | `BudClient` | *(required)* | The client instance whose `chat.completions.create()` will be instrumented |
| `capture_input` | `bool \| list[str]` | `True` | Controls which request kwargs are recorded as span attributes |
| `capture_output` | `bool \| list[str]` | `True` | Controls which response fields are recorded as span attributes |
| `span_name` | `str` | `"chat"` | Base span name. Streaming calls use `"{span_name}.stream"` |

### Return Value

Returns the same `client` object (mutated in place). Enables chaining:
```python
client = track_chat_completions(BudClient(api_key="..."))
```

### Type Alias

```python
FieldCapture = bool | list[str]
```

---

## 2. Field Capture Semantics

### Truth Table

| `capture_input` / `capture_output` | Resolved Field Set | PII Captured |
|-------------------------------------|-------------------|--------------|
| `True` | `CHAT_SAFE_INPUT_FIELDS` / `CHAT_SAFE_OUTPUT_FIELDS` | No |
| `False` | `None` (nothing captured) | No |
| `["model", "temperature"]` | `frozenset({"model", "temperature"})` | Only if list includes PII fields |
| `["model", "messages"]` | `frozenset({"model", "messages"})` | Yes — `"messages"` is PII |
| `["usage", "content"]` | `frozenset({"usage", "content"})` | Yes — `"content"` is PII |

### Resolution Function

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

Resolution happens once at patch time. The resulting `frozenset` is immutable and shared across all subsequent calls.

---

## 3. OTel Attribute Schema

### 3.1 Request Attributes

Extracted from `create(**kwargs)` keyword arguments via `_extract_chat_request_attrs()`.

| Kwarg Name | OTel Attribute Key | Value Type | Notes |
|------------|-------------------|------------|-------|
| `model` | `gen_ai.request.model` | `str` | |
| `temperature` | `gen_ai.request.temperature` | `float` | |
| `top_p` | `gen_ai.request.top_p` | `float` | |
| `max_tokens` | `gen_ai.request.max_tokens` | `int` | |
| `stop` | `gen_ai.request.stop_sequences` | `str` | `json.dumps()` when list |
| `presence_penalty` | `gen_ai.request.presence_penalty` | `float` | |
| `frequency_penalty` | `gen_ai.request.frequency_penalty` | `float` | |
| `stream` | `bud.inference.stream` | `bool` | Also set as always-on attribute |
| `messages` | `gen_ai.content.prompt` | `str` | **PII** — `json.dumps()` truncated to 1000 chars |
| `tools` | *(fallback)* `bud.inference.request.tools` | `str` | `json.dumps()` truncated |
| `tool_choice` | *(fallback)* `bud.inference.request.tool_choice` | `str` | |
| *(other)* | `bud.inference.request.{name}` | `str` | Fallback for unmapped kwargs |

**Attribute mapping constant:**
```python
CHAT_INPUT_ATTR_MAP: dict[str, str] = {
    "model": "gen_ai.request.model",
    "temperature": "gen_ai.request.temperature",
    "top_p": "gen_ai.request.top_p",
    "max_tokens": "gen_ai.request.max_tokens",
    "stop": "gen_ai.request.stop_sequences",
    "presence_penalty": "gen_ai.request.presence_penalty",
    "frequency_penalty": "gen_ai.request.frequency_penalty",
    "stream": "bud.inference.stream",
    "messages": "gen_ai.content.prompt",
}
```

### 3.2 Response Attributes

Extracted from `ChatCompletion` response via `_extract_chat_response_attrs()`.

| Response Field | OTel Attribute Key | Value Type | Source |
|---------------|-------------------|------------|--------|
| `id` | `gen_ai.response.id` | `str` | `response.id` |
| `model` | `gen_ai.response.model` | `str` | `response.model` |
| `created` | `gen_ai.response.created` | `int` | `response.created` |
| `system_fingerprint` | `gen_ai.response.system_fingerprint` | `str` | `response.system_fingerprint` (only if non-None) |
| `finish_reason` | `gen_ai.response.finish_reasons` | `list[str]` | `[response.choices[0].finish_reason]` |
| `content` | `gen_ai.content.completion` | `str` | **PII** — `response.choices[0].message.content`, truncated |

### 3.3 Usage Attributes

Extracted from `response.usage` (or final streaming chunk's usage).

| Field | OTel Attribute Key | Value Type | Source |
|-------|-------------------|------------|--------|
| *(when `"usage"` in fields)* | `gen_ai.usage.input_tokens` | `int` | `usage.prompt_tokens` |
| *(when `"usage"` in fields)* | `gen_ai.usage.output_tokens` | `int` | `usage.completion_tokens` |

### 3.4 Content Attributes (PII)

Only captured when explicitly listed in the field set.

| OTel Attribute Key | Captured When | Source | Truncation |
|-------------------|---------------|--------|------------|
| `gen_ai.content.prompt` | `"messages"` in input fields | `json.dumps(kwargs["messages"])` | 1000 chars |
| `gen_ai.content.completion` | `"content"` in output fields | `response.choices[0].message.content` or joined stream deltas | 1000 chars |

### 3.5 Bud-Specific Extension Attributes

| OTel Attribute Key | Value Type | When Set | Description |
|-------------------|------------|----------|-------------|
| `bud.inference.stream` | `bool` | Always | Whether the request is streaming |
| `bud.inference.operation` | `str` | Always | Always `"chat"` |
| `bud.inference.ttft_ms` | `float` | Streaming only | Time-to-first-token in milliseconds |
| `bud.inference.chunks` | `int` | Streaming only | Total chunks yielded |
| `bud.inference.stream_completed` | `bool` | Streaming only | `True` if stream fully consumed |

### 3.6 Always-On Attributes

These are set on every span regardless of field capture configuration:

| OTel Attribute Key | Value | Set By |
|-------------------|-------|--------|
| `gen_ai.system` | `"bud"` | `traced_create()` |
| `bud.inference.operation` | `"chat"` | `traced_create()` |
| `bud.inference.stream` | `True` / `False` | `traced_create()` |

---

## 4. Safe Default Field Sets

### Input Fields

```python
CHAT_SAFE_INPUT_FIELDS: frozenset[str] = frozenset({
    "model",
    "temperature",
    "top_p",
    "max_tokens",
    "stop",
    "presence_penalty",
    "frequency_penalty",
    "stream",
    "tool_choice",
})
```

**Excluded (PII):** `messages`, `tools`, `user`

### Output Fields

```python
CHAT_SAFE_OUTPUT_FIELDS: frozenset[str] = frozenset({
    "id",
    "model",
    "created",
    "usage",
    "system_fingerprint",
    "finish_reason",
})
```

**Excluded (PII):** `content`

---

## 5. Span Naming

| Mode | Span Name | Example |
|------|-----------|---------|
| Non-streaming | `"{span_name}"` | `"chat"` |
| Streaming | `"{span_name}.stream"` | `"chat.stream"` |

The `span_name` parameter defaults to `"chat"` and can be overridden for custom naming (e.g., `"support-chat"`, `"code-gen"`).

---

## 6. Span Lifecycle

### 6.1 Non-Streaming

```
traced_create(**kwargs) called
  │
  ├─ _is_noop()? ──True──→ original_create(**kwargs), return result
  │
  ├─ create_traced_span("chat", get_tracer("bud.inference"))
  │   → (span, context_token)
  │
  ├─ span.set_attribute("gen_ai.system", "bud")
  ├─ span.set_attribute("bud.inference.operation", "chat")
  ├─ span.set_attribute("bud.inference.stream", False)
  │
  ├─ _extract_chat_request_attrs(kwargs, input_fields)
  │   → set each k,v as span attribute
  │
  ├─ original_create(**kwargs)
  │   ├─ Exception? → _record_exception(span, exc)
  │   │               span.end()
  │   │               context.detach(token)
  │   │               raise
  │   └─ Success → result
  │
  ├─ _extract_chat_response_attrs(result, output_fields)
  │   → set each k,v as span attribute
  │   (wrapped in try/except — failure is debug-logged, never propagated)
  │
  ├─ _set_ok_status(span)
  ├─ span.end()
  ├─ context.detach(token)
  └─ return result
```

### 6.2 Streaming

```
traced_create(**kwargs) called
  │
  ├─ (Same as non-streaming through the original_create call)
  │
  ├─ original_create(**kwargs) → stream_result
  │   ├─ Exception? → same error handling as non-streaming
  │   └─ Success → stream_result
  │
  └─ return TracedChatStream(stream_result, span, token, output_fields)
      │
      │  [span is NOT ended here — it lives until iteration completes]
      │
      └─ Consumer iterates via __iter__():
           │
           ├─ First chunk:
           │   ├─ Record _first_chunk_time = time.monotonic()
           │   └─ span.set_attribute("bud.inference.ttft_ms", delta_ms)
           │
           ├─ Each chunk:
           │   ├─ _chunk_count += 1
           │   ├─ _accumulated.append(chunk)
           │   └─ yield chunk
           │
           ├─ Normal end:
           │   └─ _completed = True
           │
           ├─ GeneratorExit:
           │   └─ pass (partial completion)
           │
           ├─ Other Exception:
           │   └─ _record_exception(span, exc), raise
           │
           └─ finally → _finalize():
                ├─ if _finalized: return (guard)
                ├─ _finalized = True
                ├─ span.set_attribute("bud.inference.chunks", _chunk_count)
                ├─ span.set_attribute("bud.inference.stream_completed", _completed)
                ├─ _aggregate_stream_response(_accumulated, _output_fields)
                │   → set each k,v as span attribute
                ├─ if _completed: _set_ok_status(span)
                ├─ span.end()
                └─ context.detach(context_token)
```

---

## 7. `TracedChatStream` Contract

### Implements

| Protocol Method | Behavior |
|----------------|----------|
| `__iter__()` | Yields `ChatCompletionChunk` objects from inner stream; records TTFT, counts chunks, accumulates for aggregation |
| `__enter__()` | Returns `self` (context manager support) |
| `__exit__(*args)` | Calls `self.close()` |
| `close()` | Delegates to `self._inner.close()` (releases HTTP resources) |
| `__del__()` | Safety net — calls `_finalize()` with warning if not already finalized |

### Internal State

| Field | Type | Initial | Description |
|-------|------|---------|-------------|
| `_inner` | `Stream[ChatCompletionChunk]` | *(from constructor)* | Original stream object |
| `_span` | `Span` | *(from constructor)* | Manually-managed OTel span |
| `_context_token` | `object` | *(from constructor)* | OTel context token for `context.detach()` |
| `_output_fields` | `frozenset[str] \| None` | *(from constructor)* | Fields to extract from aggregated response |
| `_chunk_count` | `int` | `0` | Number of chunks yielded |
| `_accumulated` | `list[ChatCompletionChunk]` | `[]` | All chunks for post-stream aggregation |
| `_completed` | `bool` | `False` | `True` if stream fully consumed (no early exit) |
| `_finalized` | `bool` | `False` | Guard against double `span.end()` |
| `_start_time` | `float` | `time.monotonic()` | Timestamp for TTFT calculation |
| `_first_chunk_time` | `float \| None` | `None` | Timestamp of first chunk arrival |

### TTFT Measurement

```python
ttft_ms = (first_chunk_time - start_time) * 1000
```

`start_time` is captured at `TracedChatStream.__init__()` (immediately after `create()` returns the stream object). `first_chunk_time` is captured on the first `yield` in `__iter__()`.

---

## 8. Error Handling Matrix

| Scenario | Span Status | Exception Recorded on Span | Re-raised to Caller | `stream_completed` | Notes |
|----------|------------|--------------------------|---------------------|-------------------|-------|
| Non-streaming: HTTP 4xx/5xx | `ERROR` | Yes (`span.record_exception()`) | Yes | N/A | SDK raises `APIError` subclass |
| Non-streaming: `ConnectionError` | `ERROR` | Yes | Yes | N/A | Network failure |
| Non-streaming: `TimeoutError` | `ERROR` | Yes | Yes | N/A | Request timeout |
| Non-streaming: success | `OK` | No | No | N/A | |
| Streaming: `GeneratorExit` | *(unset)* | No | No | `False` | Consumer stopped early |
| Streaming: exception mid-stream | `ERROR` | Yes | Yes | `False` | |
| Streaming: normal completion | `OK` | No | No | `True` | |
| Streaming: HTTP error on `create()` | `ERROR` | Yes | Yes | N/A | Error before stream starts |
| Attribute extraction failure | *(no change)* | No | No | *(no change)* | `logger.debug()` only |
| Stream aggregation failure | *(no change)* | No | No | *(no change)* | `logger.debug()` only |
| OTel not installed | *(no span)* | N/A | N/A | N/A | `_is_noop()` fast path |

**Invariant:** Exceptions from the user's API call are always re-raised. Tracing failures never propagate to the user.

---

## 9. PII Rules

1. **Messages** (`gen_ai.content.prompt`) are never captured unless the user explicitly includes `"messages"` in the `capture_input` field list.

2. **Completion content** (`gen_ai.content.completion`) is never captured unless the user explicitly includes `"content"` in the `capture_output` field list.

3. **`True` (safe defaults)** excludes all PII fields. The safe field sets contain only metadata: model name, temperature, token counts, finish reason, etc.

4. **`False`** disables all attribute capture for that direction.

5. **Truncation:** When PII fields are captured, values are truncated to 1000 characters via `_safe_repr()`.

6. The `"user"` kwarg (OpenAI's user identifier) is excluded from safe defaults since it may contain PII.

---

## 10. Thread Safety

- Each call to `traced_create()` creates its own `Span` and `context_token`.
- No shared mutable state exists between concurrent calls.
- `_resolve_fields()` returns immutable `frozenset` objects shared safely across threads.
- `TracedChatStream` instances are not shared between threads (each stream belongs to one consumer).
- The `_bud_tracked` flag is set once at patch time (single-threaded setup).

---

## 11. Idempotency

- `track_chat_completions()` checks `getattr(client.chat.completions, '_bud_tracked', False)` before patching.
- If `True`, the function returns `client` immediately without modifying anything.
- The flag is set to `True` after successful patching: `client.chat.completions._bud_tracked = True`.
- This prevents double-wrapping which would create duplicate spans.

---

## 12. OTel Constant Definitions

All constants live in `src/bud/observability/_genai_attributes.py`:

```python
# OpenTelemetry GenAI Semantic Convention constants
# See: https://opentelemetry.io/docs/specs/semconv/gen-ai/

# System
GENAI_SYSTEM = "gen_ai.system"

# Request attributes
GENAI_REQUEST_MODEL = "gen_ai.request.model"
GENAI_REQUEST_TEMPERATURE = "gen_ai.request.temperature"
GENAI_REQUEST_TOP_P = "gen_ai.request.top_p"
GENAI_REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens"
GENAI_REQUEST_STOP_SEQUENCES = "gen_ai.request.stop_sequences"
GENAI_REQUEST_PRESENCE_PENALTY = "gen_ai.request.presence_penalty"
GENAI_REQUEST_FREQUENCY_PENALTY = "gen_ai.request.frequency_penalty"

# Response attributes
GENAI_RESPONSE_ID = "gen_ai.response.id"
GENAI_RESPONSE_MODEL = "gen_ai.response.model"
GENAI_RESPONSE_FINISH_REASONS = "gen_ai.response.finish_reasons"
GENAI_RESPONSE_SYSTEM_FINGERPRINT = "gen_ai.response.system_fingerprint"

# Usage attributes
GENAI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
GENAI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"

# Content attributes (PII — opt-in only)
GENAI_CONTENT_PROMPT = "gen_ai.content.prompt"
GENAI_CONTENT_COMPLETION = "gen_ai.content.completion"

# Bud-specific extensions
BUD_INFERENCE_STREAM = "bud.inference.stream"
BUD_INFERENCE_TTFT_MS = "bud.inference.ttft_ms"
BUD_INFERENCE_CHUNKS = "bud.inference.chunks"
BUD_INFERENCE_STREAM_COMPLETED = "bud.inference.stream_completed"
BUD_INFERENCE_OPERATION = "bud.inference.operation"
```

---

## 13. Dependencies

### Required (always available)

- `bud.observability._track` — `_is_noop`, `_safe_repr`, `_record_exception`, `_set_ok_status`
- `bud.observability` — `create_traced_span`, `get_tracer`
- `bud.client` — `BudClient` (type annotation only)
- `bud.models.inference` — `ChatCompletion`, `ChatCompletionChunk` (type annotations and runtime access)

### Optional (lazy-imported at call time)

- `opentelemetry.context` — for `context.detach()`
- `opentelemetry.trace` — for `StatusCode` (via `_record_exception` / `_set_ok_status`)
- `json` — for `json.dumps()` when serializing messages/tools

### Not Required at Module Import

The module can be imported without OpenTelemetry installed. All OTel imports are deferred to call time, and `_is_noop()` prevents any OTel code from executing when the library is not configured.
