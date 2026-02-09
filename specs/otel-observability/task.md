# Task List: Implement `@track` Decorator

Execute these tasks in order. Each task is atomic — complete it fully before moving to the next.

---

## Task 1: Create `_track.py` — Helpers

**File:** `src/bud/observability/_track.py`

Create the file with module docstring, imports, constants, and all helper functions.

**What to write:**

1. Module docstring (copy from spec.md)
2. Imports:
   ```python
   from __future__ import annotations
   import functools
   import inspect
   import logging
   from typing import Any, Callable, TypeVar, overload
   ```
3. Logger + TypeVar:
   ```python
   logger = logging.getLogger("bud.observability")
   F = TypeVar("F", bound=Callable[..., Any])
   ```
4. Constants:
   ```python
   _MAX_ATTR_LENGTH = 1000
   _SELF_CLS_NAMES = frozenset({"self", "cls"})
   ```
5. Helper functions (see spec.md for exact signatures and bodies):
   - `_safe_repr(value: Any) -> str`
   - `_is_noop() -> bool`
   - `_capture_inputs(fn, args, kwargs, include=None) -> dict[str, str]`
   - `_capture_output(result, include=None) -> dict[str, str]`
   - `_setup_span_attributes(span, track_type, static_attrs, input_attrs) -> None`
   - `_record_exception(span, exc) -> None`
   - `_set_ok_status(span) -> None`

**Verify:** `python3 -c "from bud.observability._track import _safe_repr, _is_noop, _capture_inputs, _capture_output; print('OK')"`

---

## Task 2: Create `_track.py` — Wrappers

**File:** `src/bud/observability/_track.py` (append to existing)

Add the four wrapper functions after the helpers.

**What to write:**

1. `_wrap_sync(fn, span_name, tracer_name, capture_input, capture_input_include, capture_output, capture_output_include, track_type, static_attrs) -> Callable`
2. `_wrap_async(...)` — identical structure with `async def wrapper` and `await fn(...)`
3. `_wrap_sync_generator(fn, span_name, tracer_name, capture_input, capture_input_include, track_type, static_attrs) -> Callable`
   - Note: No `capture_output`/`capture_output_include` params — generators don't have single return values
   - Records `bud.track.yield_count` instead
4. `_wrap_async_generator(...)` — identical to sync generator with `async def wrapper` and `async for`

**Key patterns in every wrapper:**
- `@functools.wraps(fn)` on the inner `wrapper`
- `if _is_noop(): return fn(...)` fast path (or `yield from` / `async for` for generators)
- `from bud.observability import get_tracer` inside wrapper body (deferred import)
- `with tracer.start_as_current_span(span_name) as span:` for span lifecycle
- `try/except` with `_record_exception(span, exc)` + `raise`
- `_set_ok_status(span)` on success path

**Verify:** `python3 -c "from bud.observability._track import _wrap_sync, _wrap_async, _wrap_sync_generator, _wrap_async_generator; print('OK')"`

---

## Task 3: Create `_track.py` — `track()` Decorator Factory

**File:** `src/bud/observability/_track.py` (append to existing)

Add the public `track()` function at the bottom of the file.

**What to write:**

1. Two `@overload` signatures for type checking:
   - `def track(fn: F) -> F: ...` (bare `@track`)
   - `def track(fn: None = None, *, name: str | None = None, ...) -> Callable[[F], F]: ...` (parameterized)
2. The actual `track()` implementation:
   - Parameters: `fn`, `name`, `tracer_name`, `capture_input`, `capture_input_include`, `capture_output`, `capture_output_include`, `type`, `attributes`
   - Inner `decorator(func)` function that:
     - Sets `span_name = name or func.__qualname__`
     - Checks function type with `inspect.isasyncgenfunction()`, `isgeneratorfunction()`, `iscoroutinefunction()` (in that order!)
     - Dispatches to the correct `_wrap_*` function
   - If `fn is not None`: apply decorator immediately (bare `@track`)
   - If `fn is None`: return `decorator` (parameterized case)

**Verify:** `python3 -c "from bud.observability._track import track; print(track)"`

---

## Task 4: Modify `__init__.py` — Export `track`

**File:** `src/bud/observability/__init__.py`

Two edits:

### Edit 1: Add `track` to `__getattr__`

Find the `__getattr__` function (line ~188). Add a new `if` block **after** the `TracedStream` check, **before** the `raise AttributeError`:

```python
if name == "track":
    from bud.observability._track import track
    return track
```

### Edit 2: Add `track` to `__all__`

Find the `__all__` list (line ~194). Add `"track"` as the last entry before the closing `]`.

**Verify:** `python3 -c "from bud.observability import track; print(track)"`

---

## Task 5: Create Test File — Infrastructure + Helper Tests

**File:** `tests/test_observability/test_track.py`

Create the test file with imports, the `traced_setup` fixture, and test classes for helpers.

**What to write:**

1. Imports (pytest, unittest.mock.patch, OTel SDK classes, `_track` internals)
2. `traced_setup` fixture — creates `InMemorySpanExporter` + `TracerProvider` + `SimpleSpanProcessor`, patches `_is_noop` to return `False` and `get_tracer` to use the test provider. Yields the exporter. Shuts down provider in teardown.
3. `TestSafeRepr` class — 3 tests:
   - Short string unchanged
   - Long string truncated to 1000 chars with "..."
   - Broken `__repr__` handled gracefully
4. `TestCaptureInputs` class — 7 tests:
   - Simple args → correct `bud.track.input.*` keys
   - `self` skipped
   - `cls` skipped
   - `include` filter works
   - `**kwargs` captured
   - Defaults applied
   - Non-inspectable callable returns `{}`
5. `TestCaptureOutput` class — 5 tests:
   - Scalar → `bud.track.output`
   - String → `bud.track.output`
   - Dict → `bud.track.output.<key>` per key
   - Dict with include filter → only listed keys
   - None → `bud.track.output`

**Verify:** `cd /home/budadmin/varunsr/BudAIFoundry-SDK && pytest tests/test_observability/test_track.py::TestSafeRepr -x -v`

---

## Task 6: Create Test File — Decorator Pattern + NoOp Tests

**File:** `tests/test_observability/test_track.py` (append)

Add test classes:

1. `TestTrackDecoratorPatterns` — 7 tests:
   - `@track` (bare) works
   - `@track()` (empty parens) works
   - `@track(name="x", type="llm")` (parameterized) works
   - `__name__` preserved
   - `__doc__` preserved
   - `__module__` preserved
   - `__wrapped__` set to original function

2. `TestTrackNoOp` — 4 tests (no fixture needed, `_state.is_configured` is False by default):
   - Sync function returns correct value
   - Async function returns correct value (use `asyncio.run()`)
   - Sync generator yields correct values
   - Async generator yields correct values

**Verify:** `pytest tests/test_observability/test_track.py::TestTrackDecoratorPatterns tests/test_observability/test_track.py::TestTrackNoOp -x -v`

---

## Task 7: Create Test File — Span Creation + Nesting Tests

**File:** `tests/test_observability/test_track.py` (append)

Add test classes (all use `traced_setup` fixture):

1. `TestTrackSpanCreation` — 5 tests:
   - Sync function creates 1 span
   - Async function creates 1 span
   - `@track(name="custom")` → span name is "custom"
   - Default span name is `fn.__qualname__`
   - Custom `tracer_name` passed through

2. `TestTrackNesting` — 1 test:
   - `outer()` calls `inner()` → 2 spans, inner's parent is outer

**Verify:** `pytest tests/test_observability/test_track.py::TestTrackSpanCreation tests/test_observability/test_track.py::TestTrackNesting -x -v`

---

## Task 8: Create Test File — Input/Output/Error/Generator Tests

**File:** `tests/test_observability/test_track.py` (append)

Add test classes (all use `traced_setup` fixture):

1. `TestTrackInputCapture` — 5 tests:
   - Args captured as `bud.track.input.*`
   - `self` skipped on methods
   - `capture_input=False` → no input attrs
   - `capture_input_include` filters correctly
   - Long values truncated

2. `TestTrackOutputCapture` — 4 tests:
   - Scalar captured as `bud.track.output`
   - Dict captured as `bud.track.output.*`
   - `capture_output=False` → no output attrs
   - `capture_output_include` filters dict keys

3. `TestTrackTypeAndAttributes` — 3 tests:
   - `type="llm"` → `bud.track.type` attr
   - `attributes={"env": "test"}` → static attr
   - No type → no `bud.track.type` attr

4. `TestTrackErrorHandling` — 2 tests:
   - Exception recorded on span + re-raised
   - ERROR status set with message

5. `TestTrackGenerators` — 4 tests:
   - Sync generator: `yield_count` correct
   - Sync generator: mid-iteration error → ERROR status
   - Async generator: `yield_count` correct
   - Generator: no `bud.track.output` attrs

**Verify:** `pytest tests/test_observability/test_track.py -x -v`

---

## Task 9: Create Example File

**File:** `examples/track_example.py`

Copy the example from spec.md verbatim. Ensure:
- Shebang line: `#!/usr/bin/env python3`
- Module docstring with usage instructions
- Imports from `bud` and `bud.observability`
- `@track(type="llm")` on `ask()` function
- `@track(name="pipeline", type="chain")` on `pipeline()` function
- `main()` with configure/shutdown lifecycle
- `if __name__ == "__main__": main()` guard

**Verify:** `python3 -c "import ast; ast.parse(open('examples/track_example.py').read()); print('OK')"`

---

## Task 10: Lint, Format, and Full Test Suite

Run all verification steps:

```bash
cd /home/budadmin/varunsr/BudAIFoundry-SDK

# 1. Lint + format the new module
ruff check src/bud/observability/_track.py --fix && ruff format src/bud/observability/_track.py

# 2. Lint + format tests
ruff check tests/test_observability/test_track.py --fix && ruff format tests/test_observability/test_track.py

# 3. Lint + format example
ruff check examples/track_example.py --fix && ruff format examples/track_example.py

# 4. Syntax check all new files
python3 -c "
import ast
for f in ['src/bud/observability/_track.py', 'tests/test_observability/test_track.py', 'examples/track_example.py']:
    with open(f) as fh:
        ast.parse(fh.read())
print('All files parse OK')
"

# 5. Run new tests
pytest tests/test_observability/test_track.py -x -v

# 6. Run ALL observability tests (regression check)
pytest tests/test_observability/ -x -q

# 7. Import smoke test
python3 -c "
from bud.observability import track
print(f'track imported: {track}')
print(f'track.__module__: {track.__module__}')
"
```

Fix any failures before considering the implementation complete.

---

## Summary Checklist

| # | Task | Files | Tests |
|---|------|-------|-------|
| 1 | Helpers | `_track.py` (create) | import check |
| 2 | Wrappers | `_track.py` (append) | import check |
| 3 | `track()` factory | `_track.py` (append) | import check |
| 4 | Export from `__init__` | `__init__.py` (edit) | import check |
| 5 | Helper tests | `test_track.py` (create) | pytest |
| 6 | Pattern + NoOp tests | `test_track.py` (append) | pytest |
| 7 | Span + Nesting tests | `test_track.py` (append) | pytest |
| 8 | Input/Output/Error/Gen tests | `test_track.py` (append) | pytest |
| 9 | Example | `track_example.py` (create) | ast.parse |
| 10 | Lint + full suite | all files | pytest + ruff |
