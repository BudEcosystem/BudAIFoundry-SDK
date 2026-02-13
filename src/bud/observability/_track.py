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

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
from collections.abc import Callable
from typing import Any, TypeVar, overload

logger = logging.getLogger("bud.observability")

F = TypeVar("F", bound=Callable[..., Any])

_MAX_ATTR_LENGTH = 1000
_SELF_CLS_NAMES = frozenset({"self", "cls"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_repr(value: Any) -> str:
    """Return repr(value) truncated to _MAX_ATTR_LENGTH chars."""
    try:
        text = repr(value)
    except Exception:
        text = f"<unrepresentable {type(value).__name__}>"
    if len(text) > _MAX_ATTR_LENGTH:
        return text[: _MAX_ATTR_LENGTH - 3] + "..."
    return text


def _is_noop() -> bool:
    """Return True if observability is not configured (fast path)."""
    try:
        from bud.observability._state import _state

        return not _state.is_configured
    except Exception:
        return True


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


def _aggregate_generator_output(items: list[Any]) -> str:
    """Aggregate generator items into a single output string.

    Strings are joined directly (optimal for LLM streaming chunks).
    Mixed types fall back to list repr. Result truncated via _safe_repr.
    """
    if not items:
        return _safe_repr(items)
    if all(isinstance(item, str) for item in items):
        return _safe_repr("".join(items))
    return _safe_repr(items)


def _try_aggregate_generator(
    items: list[Any],
    generations_aggregator: Callable[[list[Any]], Any] | None,
) -> str:
    """Aggregate generator items using a custom aggregator or the builtin default.

    If *generations_aggregator* is provided, it is called with the accumulated
    items.  On failure the result falls back to ``str(items)``.
    When *generations_aggregator* is ``None`` the builtin
    ``_aggregate_generator_output`` is used instead.
    """
    if generations_aggregator is not None:
        try:
            return _safe_repr(generations_aggregator(items))
        except Exception:
            logger.warning(
                "generations_aggregator failed, falling back to str(items)",
                exc_info=True,
            )
            return _safe_repr(str(items))
    return _aggregate_generator_output(items)


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


def _record_exception(span: Any, exc: BaseException) -> None:
    """Record exception on span and set ERROR status."""
    try:
        from opentelemetry.trace import StatusCode

        span.record_exception(exc)
        span.set_status(StatusCode.ERROR, str(exc))
    except Exception:
        pass


def _set_ok_status(span: Any) -> None:
    """Set span status to OK."""
    try:
        from opentelemetry.trace import StatusCode

        span.set_status(StatusCode.OK)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Wrappers
# ---------------------------------------------------------------------------


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
                _capture_inputs(fn, args, kwargs, ignore=ignore_arguments) if capture_input else {}
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
                _capture_inputs(fn, args, kwargs, ignore=ignore_arguments) if capture_input else {}
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
                _capture_inputs(fn, args, kwargs, ignore=ignore_arguments) if capture_input else {}
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
                pass  # fall through to record partial results
            except Exception as exc:
                _record_exception(span, exc)
                raise
            finally:
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
                _capture_inputs(fn, args, kwargs, ignore=ignore_arguments) if capture_input else {}
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
                pass  # fall through to record partial results
            except Exception as exc:
                _record_exception(span, exc)
                raise
            finally:
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


# ---------------------------------------------------------------------------
# Public API — track() decorator factory
# ---------------------------------------------------------------------------


@overload
def track(fn: F) -> F: ...


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
) -> Callable[[F], F]: ...


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
            output value.  Receives ``list[Any]`` of yielded items, returns a value
            whose ``repr()`` is stored as ``bud.track.output``.  Only used for
            generator-wrapped functions.  When ``None``, the builtin aggregator
            (string-join for str chunks, list repr otherwise) is used.
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
                func,
                span_name,
                tracer_name,
                capture_input,
                ignore_arguments,
                capture_output,
                generations_aggregator,
                type,
                attributes,
            )
        elif is_sync_gen:
            wrapped = _wrap_sync_generator(
                func,
                span_name,
                tracer_name,
                capture_input,
                ignore_arguments,
                capture_output,
                generations_aggregator,
                type,
                attributes,
            )
        elif is_async:
            wrapped = _wrap_async(
                func,
                span_name,
                tracer_name,
                capture_input,
                ignore_arguments,
                capture_output,
                type,
                attributes,
            )
        else:
            wrapped = _wrap_sync(
                func,
                span_name,
                tracer_name,
                capture_input,
                ignore_arguments,
                capture_output,
                type,
                attributes,
            )

        return wrapped  # type: ignore[return-value]

    # Bare @track — fn is the decorated function
    if fn is not None:
        return decorator(fn)

    # @track() or @track(name="x") — return decorator
    return decorator
