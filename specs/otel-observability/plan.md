# Plan: Create `@track` Decorator Specs for Ralph Wiggum Execution

## Deliverable

Create three files at `/home/budadmin/varunsr/BudAIFoundry-SDK/specs/otel-observability/`:
- `plan.md` — Architecture & design decisions
- `spec.md` — Detailed implementation specification (code structure, signatures, patterns)
- `task.md` — Step-by-step task list for Ralph Wiggum to execute

No code implementation — only planning documents.

## Goal

Add an Opik-style `@track` decorator so users can instrument functions with a single line instead of manual span management. Before vs after:

```python
# BEFORE (manual, 15+ lines per function)
tracer = get_tracer("my-app")
def ask(client, question):
    with tracer.start_as_current_span("ask") as span:
        span.set_attribute("question", question)
        start = time.monotonic()
        try:
            response = client.chat.completions.create(...)
            ...
        finally:
            ...

# AFTER (one decorator)
@track(type="llm")
def ask(client, question):
    response = client.chat.completions.create(...)
    return response.choices[0].message.content
```

## Key Design Decisions

1. **OTel-native** — Uses `tracer.start_as_current_span()` for parent-child nesting. No custom ContextVar stack needed (unlike Opik, which doesn't use OTel spans).

2. **No-op safe** — `_is_noop()` checks `_state.is_configured` (a single bool read). When False, calls the original function directly with zero OTel overhead. The existing `_NoOpTracer` provides a second safety layer.

3. **Function type detection at decoration time** — `inspect.isasyncgenfunction()` etc. checked once when `@track` is applied, not on every call.

4. **Deferred OTel imports** — `from bud.observability import get_tracer` happens inside the wrapper, not at module load. Matches existing codebase pattern.

## Files

| File | Action | Lines |
|------|--------|-------|
| `src/bud/observability/_track.py` | **CREATE** | ~200 |
| `src/bud/observability/__init__.py` | MODIFY (add to `__all__` + `__getattr__`) | ~5 |
| `tests/test_observability/test_track.py` | **CREATE** | ~250 |
| `examples/track_example.py` | **CREATE** (new simplified example) | ~55 |

## 1. CREATE: `src/bud/observability/_track.py`

### Module structure

```
_track.py
├── _safe_repr()              # Truncating repr for span attributes
├── _capture_inputs()         # inspect.signature().bind() → bud.track.input.* (supports ignore filter)
├── _capture_output()         # result → bud.track.output / bud.track.output.* (all-or-nothing)
├── _is_noop()                # Fast path: _state.is_configured check
├── _setup_span_attributes()  # Apply type + static + input attrs to span
├── _record_exception()       # span.record_exception() + StatusCode.ERROR
├── _set_ok_status()          # StatusCode.OK
├── _wrap_sync()              # Sync function wrapper
├── _wrap_async()             # Async coroutine wrapper
├── _wrap_sync_generator()    # Sync generator wrapper (tracks yield_count)
├── _wrap_async_generator()   # Async generator wrapper
└── track()                   # Public decorator factory (3 call patterns)
```

### Decorator factory — three call patterns

```python
@track                              # bare
@track()                            # empty parens
@track(name="x", type="llm")       # parameterized
```

Detection logic: if first positional arg is callable → bare `@track`, else → return decorator.

### Parameters

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str \| None` | `fn.__qualname__` | Span name |
| `tracer_name` | `str` | `"bud"` | OTel tracer name |
| `capture_input` | `bool` | `True` | Record args as `bud.track.input.*` |
| `ignore_arguments` | `list[str] \| None` | `None` | Exclude list of arg names. When set, these args are excluded from capture. `capture_input` must be `True`. |
| `capture_output` | `bool` | `True` | Record return as `bud.track.output` |
| `generations_aggregator` | `Callable[[list[Any]], Any] \| None` | `None` | Callback to aggregate generator items into a single output value. Only used for generator wrappers. |
| `type` | `str \| None` | `None` | Sets `bud.track.type` (e.g. `"llm"`, `"tool"`) |
| `attributes` | `dict \| None` | `None` | Static attributes added to every span |

### Wrapper dispatch (at decoration time)

```python
if inspect.isasyncgenfunction(fn):     → _wrap_async_generator
elif inspect.isgeneratorfunction(fn):  → _wrap_sync_generator
elif inspect.iscoroutinefunction(fn):  → _wrap_async
else:                                  → _wrap_sync
```

### Sync wrapper (core pattern — async is identical with `async def` + `await`)

```python
def wrapper(*args, **kwargs):
    if _is_noop():
        return fn(*args, **kwargs)

    tracer = get_tracer(tracer_name)
    with tracer.start_as_current_span(span_name) as span:
        input_attrs = _capture_inputs(fn, args, kwargs, ignore=ignore_arguments) if capture_input else {}
        _setup_span_attributes(span, type, static_attributes, input_attrs)
        try:
            result = fn(*args, **kwargs)
        except Exception as exc:
            _record_exception(span, exc)
            raise
        if capture_output:
            for k, v in _capture_output(result).items():
                span.set_attribute(k, v)
        _set_ok_status(span)
        return result
```

### Generator wrapper (sync — async is identical with `async for`)

```python
def wrapper(*args, **kwargs):
    if _is_noop():
        yield from fn(*args, **kwargs)
        return

    tracer = get_tracer(tracer_name)
    with tracer.start_as_current_span(span_name) as span:
        input_attrs = _capture_inputs(fn, args, kwargs) if capture_input else {}
        _setup_span_attributes(span, type, static_attributes, input_attrs)
        chunk_count = 0
        try:
            for item in fn(*args, **kwargs):
                chunk_count += 1
                yield item
        except Exception as exc:
            _record_exception(span, exc)
            raise
        span.set_attribute("bud.track.yield_count", chunk_count)
        _set_ok_status(span)
```

The `with` block keeps the span open for the entire iteration lifetime. No need for Opik's pop/restore trick because OTel's context manager scope naturally covers `yield`.

### Nesting — automatic via OTel

```python
@track
def outer():
    return inner()   # inner's span auto-parents to outer's span

@track
def inner():
    return 42

# Trace tree:
# outer (root)
#   └── inner (child)
```

`start_as_current_span` reads and sets the current span in `contextvars` — nesting is free.

### Input capture

- Uses `inspect.signature(fn).bind(*args, **kwargs).apply_defaults()`
- Skips `self` and `cls`
- If `ignore_arguments` is set, those args are excluded from capture:
  ```python
  # @track(ignore_arguments=["client", "temperature"])
  # def ask(client, question, model, temperature): ...
  # → only bud.track.input.question and bud.track.input.model are set
  ```
- Values stored as `repr()` truncated to 1000 chars
- Attribute prefix: `bud.track.input.<param_name>`

### Output capture

- Output capture is all-or-nothing (controlled by `capture_output` bool)
- For generators, `generations_aggregator` provides a custom callback to aggregate yielded items
- Values stored as `repr()` truncated to 1000 chars

### Error handling

- `span.record_exception(exc)` adds exception event with stack trace
- `span.set_status(StatusCode.ERROR, str(exc))`
- Exception always re-raised — decorator never swallows errors
- OTel imports inside helper with try/except fallback

## 2. MODIFY: `src/bud/observability/__init__.py`

Two changes:

**a) Add to `__getattr__`** (follows existing `TracedStream` lazy import pattern):

```python
def __getattr__(name: str) -> Any:
    if name == "TracedStream":
        return _lazy_traced_stream()
    if name == "track":
        from bud.observability._track import track
        return track
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

**b) Add to `__all__`**:

```python
__all__ = [
    ...existing entries...
    "track",
]
```

## 3. CREATE: `tests/test_observability/test_track.py`

Test groups:

| Test Class | What it validates |
|-----------|-------------------|
| `TestTrackDecoratorPatterns` | All 3 call patterns (`@track`, `@track()`, `@track(name="x")`) |
| `TestTrackNoOp` | Zero overhead when not configured (sync, async, generators) |
| `TestTrackSpanCreation` | Spans actually created with InMemorySpanExporter |
| `TestTrackNesting` | Parent-child span relationships |
| `TestTrackInputCapture` | `bud.track.input.*` attributes, `self` skipping, truncation, `ignore_arguments` exclusion |
| `TestTrackOutputCapture` | `bud.track.output` for scalars, `bud.track.output.*` for dicts, all-or-nothing capture |
| `TestTrackErrorHandling` | Exception recorded + re-raised, ERROR status |
| `TestTrackGenerators` | Sync/async generators, `yield_count`, mid-iteration errors |
| `TestTrackPreservesMetadata` | `__name__`, `__doc__`, `__module__` via `functools.wraps` |

Uses `InMemorySpanExporter` + `SimpleSpanProcessor` (pattern from existing `test_e2e.py`).

## 4. CREATE: `examples/track_example.py`

Simplified example showing the decorator API:

```python
from bud import BudClient
from bud.observability import configure, shutdown, track

@track(type="llm")
def ask(client, question):
    response = client.chat.completions.create(
        model="gpt",
        messages=[{"role": "user", "content": question}],
    )
    return response.choices[0].message.content or ""

@track(name="pipeline")
def pipeline(client):
    summary = ask(client, "Summarize quantum computing.")
    followup = ask(client, f"Explain: {summary}")
    return {"summary": summary, "followup": followup}

def main():
    configure(service_name="my-app", collector_endpoint="http://localhost:56056")
    client = BudClient(api_key="key", base_url="http://localhost:56054")
    try:
        result = pipeline(client)
        print(result)
    finally:
        client.close()
        shutdown()
```

## Attribute namespace

| Attribute | Type | Source |
|-----------|------|--------|
| `bud.track.input.<param>` | `str` | Function arguments |
| `bud.track.output` | `str` | Return value (non-dict) |
| `bud.track.output.<key>` | `str` | Return value dict keys |
| `bud.track.type` | `str` | `type` parameter |
| `bud.track.yield_count` | `int` | Generator items yielded |

## Verification

```bash
cd /home/budadmin/varunsr/BudAIFoundry-SDK

# 1. Lint + format
ruff check src/bud/observability/_track.py --fix && ruff format src/bud/observability/_track.py

# 2. Syntax check all files
python3 -c "
import ast
for f in ['src/bud/observability/_track.py', 'examples/track_example.py']:
    with open(f) as fh:
        ast.parse(fh.read())
print('OK')
"

# 3. Run new tests
pytest tests/test_observability/test_track.py -x -v

# 4. Run all observability tests (ensure no regressions)
pytest tests/test_observability/ -x -q

# 5. Run example (needs gateway + collector)
python3 examples/track_example.py
```
