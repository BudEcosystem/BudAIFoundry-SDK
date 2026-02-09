# Implementation Specification: `@track` Decorator

## File 1: `src/bud/observability/_track.py` (CREATE, ~200 lines)

### Module Docstring

```python
"""Declarative function tracing via the @track decorator.

Wraps sync/async functions and generators with OTel spans.
Automatically captures inputs, outputs, and errors as span attributes.

Usage:
    from bud.observability import track

    @track
    def my_function(x, y):
        return x + y

    @track(name="custom-name", type="llm", capture_input=True)
    def ask(client, question):
        return client.chat.completions.create(...)
"""
```

### Imports

```python
from __future__ import annotations

import functools
import inspect
import logging
from typing import Any, Callable, TypeVar, overload

logger = logging.getLogger("bud.observability")

F = TypeVar("F", bound=Callable[..., Any])
```

No OTel imports at module level. All OTel access goes through `bud.observability.get_tracer` imported inside wrapper bodies.

### Constants

```python
_MAX_ATTR_LENGTH = 1000
_SELF_CLS_NAMES = frozenset({"self", "cls"})
```

---

### Helper: `_safe_repr(value: Any) -> str`

Truncating repr for span attributes.

```python
def _safe_repr(value: Any) -> str:
    """Return repr(value) truncated to _MAX_ATTR_LENGTH chars."""
    try:
        text = repr(value)
    except Exception:
        text = f"<unrepresentable {type(value).__name__}>"
    if len(text) > _MAX_ATTR_LENGTH:
        return text[:_MAX_ATTR_LENGTH - 3] + "..."
    return text
```

---

### Helper: `_is_noop() -> bool`

Fast path check. Single bool read, no lock.

```python
def _is_noop() -> bool:
    """Return True if observability is not configured (fast path)."""
    try:
        from bud.observability._state import _state
        return not _state.is_configured
    except Exception:
        return True
```

**Note:** The `try/except` handles the edge case where `_state` import fails (e.g., corrupted install). Returns `True` (noop) on failure — never breaks user code.

---

### Helper: `_capture_inputs(fn, args, kwargs, ignore=None) -> dict[str, str]`

Uses `inspect.signature` to map positional/keyword args to parameter names.

```python
def _capture_inputs(
    fn: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    ignore: list[str] | None = None,
) -> dict[str, str]:
    """Bind args to param names and return as bud.track.input.* attributes.

    Skips 'self' and 'cls'. Applies ignore filter if provided.
    Returns empty dict on any introspection failure.
    """
    try:
        sig = inspect.signature(fn)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
    except (ValueError, TypeError):
        logger.debug("Could not bind arguments for %s", getattr(fn, "__qualname__", fn))
        return {}

    attrs: dict[str, str] = {}
    for name, value in bound.arguments.items():
        if name in _SELF_CLS_NAMES:
            continue
        if ignore is not None and name in ignore:
            continue
        attrs[f"bud.track.input.{name}"] = _safe_repr(value)
    return attrs
```

**Behavior:**
- `@track` on `def foo(self, x, y)` → captures `bud.track.input.x`, `bud.track.input.y` (skips `self`)
- `@track(ignore_arguments=["x"])` on `def foo(x, y, z)` → captures `bud.track.input.y`, `bud.track.input.z` (excludes `x`)
- If `inspect.signature` fails (C extension, weird `__call__`) → returns `{}`, logs debug

---

### Helper: `_capture_output(result) -> dict[str, str]`

```python
def _capture_output(result: Any) -> dict[str, str]:
    """Convert return value to bud.track.output.* attributes.

    - Dict return: all keys captured as bud.track.output.<key>
    - Non-dict return: single bud.track.output attribute
    """
    if isinstance(result, dict):
        attrs: dict[str, str] = {}
        for key, value in result.items():
            attrs[f"bud.track.output.{key}"] = _safe_repr(value)
        return attrs
    return {"bud.track.output": _safe_repr(result)}
```

**Behavior:**
- `return {"answer": "yes", "score": 0.9}` → `bud.track.output.answer`, `bud.track.output.score`
- `return "hello"` → `bud.track.output = "'hello'"`
- `return 42` → `bud.track.output = "42"`

---

### Helper: `_setup_span_attributes(span, type, static_attrs, input_attrs)`

```python
def _setup_span_attributes(
    span: Any,
    track_type: str | None,
    static_attrs: dict[str, Any] | None,
    input_attrs: dict[str, str],
) -> None:
    """Apply type, static, and input attributes to span."""
    if track_type is not None:
        span.set_attribute("bud.track.type", track_type)
    if static_attrs:
        for k, v in static_attrs.items():
            span.set_attribute(k, v)
    for k, v in input_attrs.items():
        span.set_attribute(k, v)
```

---

### Helper: `_record_exception(span, exc)`

```python
def _record_exception(span: Any, exc: BaseException) -> None:
    """Record exception on span and set ERROR status."""
    try:
        from opentelemetry.trace import StatusCode
        span.record_exception(exc)
        span.set_status(StatusCode.ERROR, str(exc))
    except Exception:
        # Fallback if OTel import fails — span is likely a _NoOpSpan anyway
        pass
```

---

### Helper: `_set_ok_status(span)`

```python
def _set_ok_status(span: Any) -> None:
    """Set span status to OK."""
    try:
        from opentelemetry.trace import StatusCode
        span.set_status(StatusCode.OK)
    except Exception:
        pass
```

---

### Wrapper: `_wrap_sync(fn, span_name, tracer_name, capture_input, ignore_arguments, capture_output, track_type, static_attrs)`

```python
def _wrap_sync(
    fn: Callable[..., Any],
    span_name: str,
    tracer_name: str,
    capture_input: bool,
    ignore_arguments: list[str] | None,
    capture_output: bool,
    track_type: str | None,
    static_attrs: dict[str, Any] | None,
) -> Callable[..., Any]:
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if _is_noop():
            return fn(*args, **kwargs)

        from bud.observability import get_tracer

        tracer = get_tracer(tracer_name)
        with tracer.start_as_current_span(span_name) as span:
            input_attrs = (
                _capture_inputs(fn, args, kwargs, ignore=ignore_arguments)
                if capture_input
                else {}
            )
            _setup_span_attributes(span, track_type, static_attrs, input_attrs)
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

    return wrapper
```

---

### Wrapper: `_wrap_async(fn, ...)`

Identical structure to `_wrap_sync` but with `async def wrapper` and `await fn(...)`.

```python
def _wrap_async(
    fn: Callable[..., Any],
    span_name: str,
    tracer_name: str,
    capture_input: bool,
    ignore_arguments: list[str] | None,
    capture_output: bool,
    track_type: str | None,
    static_attrs: dict[str, Any] | None,
) -> Callable[..., Any]:
    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        if _is_noop():
            return await fn(*args, **kwargs)

        from bud.observability import get_tracer

        tracer = get_tracer(tracer_name)
        with tracer.start_as_current_span(span_name) as span:
            input_attrs = (
                _capture_inputs(fn, args, kwargs, ignore=ignore_arguments)
                if capture_input
                else {}
            )
            _setup_span_attributes(span, track_type, static_attrs, input_attrs)
            try:
                result = await fn(*args, **kwargs)
            except Exception as exc:
                _record_exception(span, exc)
                raise
            if capture_output:
                for k, v in _capture_output(result).items():
                    span.set_attribute(k, v)
            _set_ok_status(span)
            return result

    return wrapper
```

---

### Wrapper: `_wrap_sync_generator(fn, ...)`

```python
def _wrap_sync_generator(
    fn: Callable[..., Any],
    span_name: str,
    tracer_name: str,
    capture_input: bool,
    ignore_arguments: list[str] | None,
    capture_output: bool,
    generations_aggregator: Callable[[list[Any]], Any] | None,
    track_type: str | None,
    static_attrs: dict[str, Any] | None,
) -> Callable[..., Any]:
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if _is_noop():
            yield from fn(*args, **kwargs)
            return

        from bud.observability import get_tracer

        tracer = get_tracer(tracer_name)
        with tracer.start_as_current_span(span_name) as span:
            input_attrs = (
                _capture_inputs(fn, args, kwargs, ignore=ignore_arguments)
                if capture_input
                else {}
            )
            _setup_span_attributes(span, track_type, static_attrs, input_attrs)
            chunk_count = 0
            accumulated: list[Any] = []
            completed = False
            try:
                for item in fn(*args, **kwargs):
                    chunk_count += 1
                    if capture_output:
                        accumulated.append(item)
                    yield item
                completed = True
            except GeneratorExit:
                pass
            except Exception as exc:
                _record_exception(span, exc)
                raise
            span.set_attribute("bud.track.yield_count", chunk_count)
            span.set_attribute("bud.track.generator_completed", completed)
            if capture_output and accumulated:
                try:
                    span.set_attribute(
                        "bud.track.output",
                        _try_aggregate_generator(accumulated, generations_aggregator),
                    )
                except Exception:
                    logger.debug("Failed to capture generator output", exc_info=True)
            if completed:
                _set_ok_status(span)

    return wrapper
```

**Note:** Generator wrappers accept `generations_aggregator` to customize how yielded items are aggregated into the `bud.track.output` attribute. When `None`, the builtin aggregator (string-join for str chunks, list repr otherwise) is used.

---

### Wrapper: `_wrap_async_generator(fn, ...)`

Identical to sync generator but uses `async def wrapper`, `async for item in fn(...)`.

```python
def _wrap_async_generator(
    fn: Callable[..., Any],
    span_name: str,
    tracer_name: str,
    capture_input: bool,
    ignore_arguments: list[str] | None,
    capture_output: bool,
    generations_aggregator: Callable[[list[Any]], Any] | None,
    track_type: str | None,
    static_attrs: dict[str, Any] | None,
) -> Callable[..., Any]:
    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        if _is_noop():
            async for item in fn(*args, **kwargs):
                yield item
            return

        from bud.observability import get_tracer

        tracer = get_tracer(tracer_name)
        with tracer.start_as_current_span(span_name) as span:
            input_attrs = (
                _capture_inputs(fn, args, kwargs, ignore=ignore_arguments)
                if capture_input
                else {}
            )
            _setup_span_attributes(span, track_type, static_attrs, input_attrs)
            chunk_count = 0
            accumulated: list[Any] = []
            completed = False
            try:
                async for item in fn(*args, **kwargs):
                    chunk_count += 1
                    if capture_output:
                        accumulated.append(item)
                    yield item
                completed = True
            except (GeneratorExit, asyncio.CancelledError):
                pass
            except Exception as exc:
                _record_exception(span, exc)
                raise
            span.set_attribute("bud.track.yield_count", chunk_count)
            span.set_attribute("bud.track.generator_completed", completed)
            if capture_output and accumulated:
                try:
                    span.set_attribute(
                        "bud.track.output",
                        _try_aggregate_generator(accumulated, generations_aggregator),
                    )
                except Exception:
                    logger.debug("Failed to capture generator output", exc_info=True)
            if completed:
                _set_ok_status(span)

    return wrapper
```

---

### Public API: `track()` — Decorator Factory

Supports three call patterns via `@overload`:

```python
@overload
def track(fn: F) -> F: ...                    # @track (bare)

@overload
def track(
    fn: None = None,
    *,
    name: str | None = None,
    tracer_name: str = "bud",
    capture_input: bool = True,
    ignore_arguments: list[str] | None = None,
    capture_output: bool = True,
    generations_aggregator: Callable[[list[Any]], Any] | None = None,
    type: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> Callable[[F], F]: ...                    # @track() or @track(name="x")

def track(
    fn: F | None = None,
    *,
    name: str | None = None,
    tracer_name: str = "bud",
    capture_input: bool = True,
    ignore_arguments: list[str] | None = None,
    capture_output: bool = True,
    generations_aggregator: Callable[[list[Any]], Any] | None = None,
    type: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> F | Callable[[F], F]:
    """Decorator that wraps a function with an OTel span.

    Supports sync/async functions and sync/async generators.

    Args:
        fn: The function to decorate (set automatically for bare @track).
        name: Span name. Defaults to fn.__qualname__.
        tracer_name: OTel tracer name. Defaults to "bud".
        capture_input: Record function args as bud.track.input.* attributes.
        ignore_arguments: List of arg names to exclude from capture (None = capture all).
        capture_output: Record return value as bud.track.output attribute(s).
        generations_aggregator: Callback to aggregate generator items into a single
            output value. Only used for generator-wrapped functions.
        type: Sets bud.track.type attribute (e.g. "llm", "tool", "chain").
        attributes: Static attributes added to every span invocation.

    Examples:
        @track
        def simple(): ...

        @track()
        def also_simple(): ...

        @track(name="ask-llm", type="llm", ignore_arguments=["client", "api_key"])
        def ask(client, question, api_key): ...

        @track(type="tool")
        async def fetch_data(url): ...
    """

    def decorator(func: F) -> F:
        span_name = name or func.__qualname__
        is_async_gen = inspect.isasyncgenfunction(func)
        is_sync_gen = inspect.isgeneratorfunction(func)
        is_async = inspect.iscoroutinefunction(func)

        if is_async_gen:
            wrapped = _wrap_async_generator(
                func, span_name, tracer_name,
                capture_input, ignore_arguments,
                capture_output, generations_aggregator,
                type, attributes,
            )
        elif is_sync_gen:
            wrapped = _wrap_sync_generator(
                func, span_name, tracer_name,
                capture_input, ignore_arguments,
                capture_output, generations_aggregator,
                type, attributes,
            )
        elif is_async:
            wrapped = _wrap_async(
                func, span_name, tracer_name,
                capture_input, ignore_arguments,
                capture_output,
                type, attributes,
            )
        else:
            wrapped = _wrap_sync(
                func, span_name, tracer_name,
                capture_input, ignore_arguments,
                capture_output,
                type, attributes,
            )

        return wrapped  # type: ignore[return-value]

    # Bare @track — fn is the decorated function
    if fn is not None:
        return decorator(fn)

    # @track() or @track(name="x") — return decorator
    return decorator  # type: ignore[return-value]
```

**Detection logic:**
- `@track` → Python calls `track(fn)` with the function as first positional arg → `fn is not None` → apply decorator immediately
- `@track()` → Python calls `track()` → `fn is None` → return `decorator`
- `@track(name="x")` → Python calls `track(name="x")` → `fn is None` → return `decorator`

---

## File 2: `src/bud/observability/__init__.py` (MODIFY, ~5 lines)

### Change 1: Add to `__getattr__`

**Current code (lines 188-191):**
```python
def __getattr__(name: str) -> Any:
    if name == "TracedStream":
        return _lazy_traced_stream()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

**New code:**
```python
def __getattr__(name: str) -> Any:
    if name == "TracedStream":
        return _lazy_traced_stream()
    if name == "track":
        from bud.observability._track import track
        return track
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

### Change 2: Add to `__all__`

**Current code (lines 194-209):**
```python
__all__ = [
    "configure",
    "shutdown",
    ...
    "TracedStream",
]
```

**New code — add `"track"` at the end:**
```python
__all__ = [
    "configure",
    "shutdown",
    ...
    "TracedStream",
    "track",
]
```

---

## File 3: `tests/test_observability/test_track.py` (CREATE, ~250 lines)

### Test Infrastructure (module-level fixtures)

```python
"""Tests for the @track decorator."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from bud.observability._track import (
    _capture_inputs,
    _capture_output,
    _is_noop,
    _safe_repr,
    track,
)
```

### Fixture: `traced_setup`

Shared fixture that creates a TracerProvider + InMemorySpanExporter, patches `_state.is_configured = True` and `get_tracer` to return a real tracer from that provider. Yields the exporter for span inspection. Shuts down provider in teardown.

```python
@pytest.fixture
def traced_setup():
    """Provide a real TracerProvider with InMemorySpanExporter.

    Patches _state.is_configured to True and get_tracer to return
    a tracer from this provider, so @track creates real spans.
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    def _get_tracer(name="bud"):
        return provider.get_tracer(name)

    with (
        patch("bud.observability._track._is_noop", return_value=False),
        patch("bud.observability._track.get_tracer", side_effect=_get_tracer),
    ):
        # Note: we patch get_tracer at the _track module level since
        # the wrapper does `from bud.observability import get_tracer`
        # which resolves via the module, but the deferred import inside
        # the wrapper body means we need to patch where it's looked up.
        yield exporter

    provider.shutdown()
```

**Alternative approach if the deferred import pattern makes patching tricky:** Patch `bud.observability.get_tracer` instead, since that's what the wrapper imports. Test both approaches during implementation and use whichever works.

---

### Test Class: `TestSafeRepr`

```
test_short_string_unchanged         — repr("hello") stays as-is
test_long_string_truncated          — 2000-char string truncated to 1000 with "..."
test_unrepresentable_object         — object with broken __repr__ → "<unrepresentable ...>"
```

---

### Test Class: `TestCaptureInputs`

```
test_simple_args                    — def foo(x, y): ... → bud.track.input.x, bud.track.input.y
test_skips_self                     — def foo(self, x): ... → only bud.track.input.x
test_skips_cls                      — def foo(cls, x): ... → only bud.track.input.x
test_include_filter                 — include=["x"] on def foo(x, y, z) → only bud.track.input.x
test_kwargs_captured                — def foo(**kw): called with a=1 → bud.track.input.kw
test_defaults_applied               — def foo(x, y=10): called with (1,) → captures y=10
test_signature_failure_returns_empty — non-inspectable callable → {}
```

---

### Test Class: `TestCaptureOutput`

```
test_scalar_return                  — return 42 → {"bud.track.output": "42"}
test_string_return                  — return "hi" → {"bud.track.output": "'hi'"}
test_dict_return                    — return {"a": 1, "b": 2} → bud.track.output.a, bud.track.output.b
test_dict_with_include              — include=["a"] → only bud.track.output.a
test_none_return                    — return None → {"bud.track.output": "None"}
```

---

### Test Class: `TestTrackDecoratorPatterns`

```
test_bare_decorator                 — @track on sync function → callable, __name__ preserved
test_empty_parens                   — @track() → same behavior
test_parameterized                  — @track(name="x", type="llm") → callable, __name__ preserved
test_preserves_name                 — decorated.__name__ == original.__name__
test_preserves_doc                  — decorated.__doc__ == original.__doc__
test_preserves_module               — decorated.__module__ == original.__module__
test_preserves_wrapped              — decorated.__wrapped__ is original
```

---

### Test Class: `TestTrackNoOp`

All tests verify that when `_is_noop()` returns True, the function runs normally with zero OTel overhead.

```
test_sync_noop                      — @track sync function returns correct value
test_async_noop                     — @track async function returns correct value
test_sync_generator_noop            — @track generator yields correct values
test_async_generator_noop           — @track async generator yields correct values
```

Implementation pattern:
```python
def test_sync_noop(self):
    @track
    def add(x, y):
        return x + y

    # _state.is_configured is False by default → noop
    assert add(2, 3) == 5
```

---

### Test Class: `TestTrackSpanCreation`

Uses `traced_setup` fixture.

```
test_sync_creates_span              — exporter.get_finished_spans() has 1 span with correct name
test_async_creates_span             — same for async function
test_custom_name                    — @track(name="custom") → span.name == "custom"
test_default_name_is_qualname       — @track → span.name == fn.__qualname__
test_custom_tracer_name             — @track(tracer_name="my-tracer") → get_tracer called with "my-tracer"
```

---

### Test Class: `TestTrackNesting`

Uses `traced_setup` fixture.

```
test_parent_child_relationship      — outer() calls inner() → 2 spans, inner.parent == outer
```

Implementation:
```python
def test_parent_child_relationship(self, traced_setup):
    exporter = traced_setup

    @track(name="outer")
    def outer():
        return inner()

    @track(name="inner")
    def inner():
        return 42

    result = outer()
    assert result == 42

    spans = exporter.get_finished_spans()
    assert len(spans) == 2

    # Spans are exported in finish order: inner first, then outer
    inner_span = next(s for s in spans if s.name == "inner")
    outer_span = next(s for s in spans if s.name == "outer")

    assert inner_span.parent is not None
    assert inner_span.parent.span_id == outer_span.context.span_id
```

---

### Test Class: `TestTrackInputCapture`

Uses `traced_setup` fixture.

```
test_captures_args                  — bud.track.input.x == repr(value)
test_skips_self_in_method           — method on class → self not captured
test_capture_input_false            — @track(capture_input=False) → no bud.track.input.* attrs
test_ignore_arguments          — only listed args captured
test_truncates_long_values          — 2000-char arg truncated to 1000
```

---

### Test Class: `TestTrackOutputCapture`

Uses `traced_setup` fixture.

```
test_captures_scalar                — bud.track.output == repr(42)
test_captures_dict_keys             — bud.track.output.a, bud.track.output.b
test_capture_output_false           — @track(capture_output=False) → no bud.track.output* attrs
test_generations_aggregator         — only listed dict keys captured
```

---

### Test Class: `TestTrackTypeAndAttributes`

Uses `traced_setup` fixture.

```
test_type_attribute                 — @track(type="llm") → bud.track.type == "llm"
test_static_attributes              — @track(attributes={"env": "test"}) → env == "test"
test_no_type_no_attribute           — @track → no bud.track.type attr set
```

---

### Test Class: `TestTrackErrorHandling`

Uses `traced_setup` fixture.

```
test_exception_recorded_and_reraised — span has exception event + ERROR status, exception propagates
test_error_status_message           — span.status.description == str(exc)
```

Implementation:
```python
def test_exception_recorded_and_reraised(self, traced_setup):
    exporter = traced_setup

    @track(name="failing")
    def failing():
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        failing()

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]

    # Check ERROR status
    from opentelemetry.trace import StatusCode
    assert span.status.status_code == StatusCode.ERROR

    # Check exception event recorded
    events = span.events
    assert len(events) == 1
    assert events[0].name == "exception"
```

---

### Test Class: `TestTrackGenerators`

Uses `traced_setup` fixture.

```
test_sync_generator_yield_count     — yields 3 items → bud.track.yield_count == 3
test_sync_generator_mid_error       — error after 2 yields → yield_count not set, ERROR status
test_async_generator_yield_count    — async yields 3 → bud.track.yield_count == 3
test_generator_no_output_capture    — no bud.track.output attrs on generators
```

Implementation:
```python
def test_sync_generator_yield_count(self, traced_setup):
    exporter = traced_setup

    @track(name="gen")
    def gen():
        yield 1
        yield 2
        yield 3

    result = list(gen())
    assert result == [1, 2, 3]

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert dict(spans[0].attributes)["bud.track.yield_count"] == 3
```

---

## File 4: `examples/track_example.py` (CREATE, ~55 lines)

```python
#!/usr/bin/env python3
"""Simplified AI assistant example using the @track decorator.

Compare with observability_example.py which uses manual span management.
The @track decorator reduces per-function boilerplate from ~15 lines to 1 line.

Usage:
    BUD_API_KEY=your-key python examples/track_example.py
"""

from __future__ import annotations

import os

from bud import BudClient
from bud.observability import configure, shutdown, track

BASE_URL = os.environ.get("BUD_BASE_URL", "http://localhost:56054")
API_KEY = os.environ.get("BUD_API_KEY", "my-test-api-key")
OTEL_ENDPOINT = os.environ.get("BUD_OTEL_ENDPOINT", "http://localhost:56056")


@track(type="llm")
def ask(client: BudClient, question: str) -> str:
    """Ask a question and return the response. Automatically traced."""
    response = client.chat.completions.create(
        model="gpt",
        messages=[{"role": "user", "content": question}],
        temperature=0.3,
        max_tokens=256,
    )
    return response.choices[0].message.content or ""


@track(name="pipeline", type="chain")
def pipeline(client: BudClient) -> dict[str, str]:
    """Multi-step pipeline. Each @track call nests as a child span."""
    summary = ask(client, "Summarize quantum computing in one sentence.")
    followup = ask(client, f"Explain this further: {summary}")
    return {"summary": summary, "followup": followup}


def main() -> None:
    configure(service_name="track-example", collector_endpoint=OTEL_ENDPOINT)
    client = BudClient(api_key=API_KEY, base_url=BASE_URL)

    try:
        result = pipeline(client)
        print(f"Summary:  {result['summary']}")
        print(f"Followup: {result['followup']}")
    finally:
        client.close()
        shutdown()

    print("\nDone. Check your collector for traces:")
    print("  pipeline (root)")
    print("    -> ask (child, question='Summarize...')")
    print("    -> ask (child, question='Explain...')")


if __name__ == "__main__":
    main()
```

---

## Attribute Reference

| Attribute Key | Type | When Set | Source |
|---|---|---|---|
| `bud.track.input.<param>` | `str` | `capture_input=True` | `inspect.signature().bind()` via `_capture_inputs()` |
| `bud.track.output` | `str` | `capture_output=True`, non-dict return | `_capture_output()` |
| `bud.track.output.<key>` | `str` | `capture_output=True`, dict return | `_capture_output()` |
| `bud.track.type` | `str` | `type` parameter provided | `_setup_span_attributes()` |
| `bud.track.yield_count` | `int` | Generator wrappers only | `_wrap_sync_generator()` / `_wrap_async_generator()` |
| User-defined keys | `Any` | `attributes` parameter provided | `_setup_span_attributes()` |

## Import Graph

```
bud.observability (public API)
  └── __getattr__("track")
        └── bud.observability._track (new module)
              ├── inspect (stdlib, at module level)
              ├── functools (stdlib, at module level)
              ├── logging (stdlib, at module level)
              └── [inside wrapper body, deferred]:
                    ├── bud.observability.get_tracer
                    ├── bud.observability._state._state
                    └── opentelemetry.trace.StatusCode
```
