"""Tests for the @track decorator."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from bud.observability._track import (
    _aggregate_generator_output,
    _capture_inputs,
    _capture_output,
    _safe_repr,
    _try_aggregate_generator,
    track,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def traced_setup():
    """Provide a real TracerProvider with InMemorySpanExporter.

    Patches _is_noop to return False and get_tracer to return
    a tracer from this provider, so @track creates real spans.
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    def _get_tracer(name="bud"):
        return provider.get_tracer(name)

    with (
        patch("bud.observability._track._is_noop", return_value=False),
        patch("bud.observability.get_tracer", side_effect=_get_tracer),
    ):
        yield exporter

    provider.shutdown()


# ---------------------------------------------------------------------------
# Helper tests
# ---------------------------------------------------------------------------


class TestSafeRepr:
    def test_short_string_unchanged(self):
        assert _safe_repr("hello") == "'hello'"

    def test_long_string_truncated(self):
        long_val = "x" * 2000
        result = _safe_repr(long_val)
        assert len(result) == 1000
        assert result.endswith("...")

    def test_unrepresentable_object(self):
        class Bad:
            def __repr__(self):
                raise RuntimeError("boom")

        result = _safe_repr(Bad())
        assert result == "<unrepresentable Bad>"


class TestAggregateGeneratorOutput:
    def test_empty_list(self):
        assert _aggregate_generator_output([]) == "[]"

    def test_all_strings_joined(self):
        assert _aggregate_generator_output(["Hello", " ", "world"]) == "'Hello world'"

    def test_mixed_types_list_repr(self):
        assert _aggregate_generator_output([1, "two", 3]) == "[1, 'two', 3]"

    def test_single_string(self):
        assert _aggregate_generator_output(["hi"]) == "'hi'"

    def test_single_int(self):
        assert _aggregate_generator_output([42]) == "[42]"


class TestCaptureInputs:
    def test_simple_args(self):
        def foo(x, y):
            pass

        result = _capture_inputs(foo, (1, 2), {})
        assert result == {"bud.track.input.x": "1", "bud.track.input.y": "2"}

    def test_skips_self(self):
        def foo(self, x):
            pass

        result = _capture_inputs(foo, ("instance", 42), {})
        assert result == {"bud.track.input.x": "42"}
        assert "bud.track.input.self" not in result

    def test_skips_cls(self):
        def foo(cls, x):
            pass

        result = _capture_inputs(foo, ("MyClass", 42), {})
        assert result == {"bud.track.input.x": "42"}
        assert "bud.track.input.cls" not in result

    def test_ignore_filter(self):
        def foo(x, y, z):
            pass

        result = _capture_inputs(foo, (1, 2, 3), {}, ignore=["y"])
        assert result == {"bud.track.input.x": "1", "bud.track.input.z": "3"}
        assert "bud.track.input.y" not in result

    def test_kwargs_captured(self):
        def foo(**kw):
            pass

        result = _capture_inputs(foo, (), {"a": 1})
        assert "bud.track.input.kw" in result

    def test_defaults_applied(self):
        def foo(x, y=10):
            pass

        result = _capture_inputs(foo, (1,), {})
        assert result == {"bud.track.input.x": "1", "bud.track.input.y": "10"}

    def test_signature_failure_returns_empty(self):
        # Create a callable that can't be inspected
        class NoSig:
            __signature__ = None

            def __call__(self):
                pass

        nosig = NoSig()
        result = _capture_inputs(nosig, (), {})
        assert result == {}


class TestCaptureOutput:
    def test_scalar_return(self):
        assert _capture_output(42) == {"bud.track.output": "42"}

    def test_string_return(self):
        assert _capture_output("hi") == {"bud.track.output": "'hi'"}

    def test_dict_return(self):
        result = _capture_output({"a": 1, "b": 2})
        assert result == {"bud.track.output.a": "1", "bud.track.output.b": "2"}

    def test_none_return(self):
        assert _capture_output(None) == {"bud.track.output": "None"}


# ---------------------------------------------------------------------------
# Decorator pattern tests
# ---------------------------------------------------------------------------


class TestTrackDecoratorPatterns:
    def test_bare_decorator(self):
        @track
        def add(x, y):
            """Add two numbers."""
            return x + y

        assert callable(add)
        assert add.__name__ == "add"

    def test_empty_parens(self):
        @track()
        def add(x, y):
            return x + y

        assert callable(add)
        assert add.__name__ == "add"

    def test_parameterized(self):
        @track(name="custom", type="llm")
        def add(x, y):
            return x + y

        assert callable(add)
        assert add.__name__ == "add"

    def test_preserves_name(self):
        @track
        def my_func():
            pass

        assert my_func.__name__ == "my_func"

    def test_preserves_doc(self):
        @track
        def my_func():
            """My docstring."""

        assert my_func.__doc__ == "My docstring."

    def test_preserves_module(self):
        @track
        def my_func():
            pass

        assert my_func.__module__ == __name__

    def test_preserves_wrapped(self):
        def original():
            pass

        decorated = track(original)
        assert decorated.__wrapped__ is original


# ---------------------------------------------------------------------------
# No-op tests (default state: not configured)
# ---------------------------------------------------------------------------


class TestTrackNoOp:
    def test_sync_noop(self):
        @track
        def add(x, y):
            return x + y

        assert add(2, 3) == 5

    def test_async_noop(self):
        @track
        async def add(x, y):
            return x + y

        assert asyncio.run(add(2, 3)) == 5

    def test_sync_generator_noop(self):
        @track
        def gen():
            yield 1
            yield 2
            yield 3

        assert list(gen()) == [1, 2, 3]

    def test_async_generator_noop(self):
        @track
        async def gen():
            yield 1
            yield 2
            yield 3

        async def collect():
            return [item async for item in gen()]

        assert asyncio.run(collect()) == [1, 2, 3]


# ---------------------------------------------------------------------------
# Span creation tests
# ---------------------------------------------------------------------------


class TestTrackSpanCreation:
    def test_sync_creates_span(self, traced_setup):
        exporter = traced_setup

        @track(name="my-span")
        def add(x, y):
            return x + y

        assert add(1, 2) == 3
        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "my-span"

    def test_async_creates_span(self, traced_setup):
        exporter = traced_setup

        @track(name="async-span")
        async def add(x, y):
            return x + y

        assert asyncio.run(add(1, 2)) == 3
        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "async-span"

    def test_custom_name(self, traced_setup):
        exporter = traced_setup

        @track(name="custom")
        def foo():
            return 1

        foo()
        spans = exporter.get_finished_spans()
        assert spans[0].name == "custom"

    def test_default_name_is_qualname(self, traced_setup):
        exporter = traced_setup

        @track
        def my_function():
            return 1

        my_function()
        spans = exporter.get_finished_spans()
        assert (
            spans[0].name
            == "TestTrackSpanCreation.test_default_name_is_qualname.<locals>.my_function"
        )

    def test_custom_tracer_name(self, traced_setup):
        exporter = traced_setup

        @track(tracer_name="my-tracer")
        def foo():
            return 1

        foo()
        spans = exporter.get_finished_spans()
        assert len(spans) == 1


# ---------------------------------------------------------------------------
# Nesting tests
# ---------------------------------------------------------------------------


class TestTrackNesting:
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

        inner_span = next(s for s in spans if s.name == "inner")
        outer_span = next(s for s in spans if s.name == "outer")

        assert inner_span.parent is not None
        assert inner_span.parent.span_id == outer_span.context.span_id


# ---------------------------------------------------------------------------
# Input capture tests
# ---------------------------------------------------------------------------


class TestTrackInputCapture:
    def test_captures_args(self, traced_setup):
        exporter = traced_setup

        @track(name="fn")
        def fn(x, y):
            return x + y

        fn(1, 2)
        spans = exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs["bud.track.input.x"] == "1"
        assert attrs["bud.track.input.y"] == "2"

    def test_skips_self_in_method(self, traced_setup):
        exporter = traced_setup

        class MyClass:
            @track(name="method")
            def method(self, x):
                return x

        obj = MyClass()
        obj.method(42)
        spans = exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert "bud.track.input.self" not in attrs
        assert attrs["bud.track.input.x"] == "42"

    def test_capture_input_false(self, traced_setup):
        exporter = traced_setup

        @track(name="fn", capture_input=False)
        def fn(x, y):
            return x + y

        fn(1, 2)
        spans = exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert "bud.track.input.x" not in attrs
        assert "bud.track.input.y" not in attrs

    def test_ignore_arguments(self, traced_setup):
        exporter = traced_setup

        @track(name="fn", ignore_arguments=["y", "z"])
        def fn(x, y, z):  # noqa: ARG001
            return x

        fn(1, 2, 3)
        spans = exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs["bud.track.input.x"] == "1"
        assert "bud.track.input.y" not in attrs
        assert "bud.track.input.z" not in attrs

    def test_truncates_long_values(self, traced_setup):
        exporter = traced_setup

        @track(name="fn")
        def fn(x):
            return x

        fn("a" * 2000)
        spans = exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        val = attrs["bud.track.input.x"]
        assert len(val) == 1000
        assert val.endswith("...")


# ---------------------------------------------------------------------------
# Output capture tests
# ---------------------------------------------------------------------------


class TestTrackOutputCapture:
    def test_captures_scalar(self, traced_setup):
        exporter = traced_setup

        @track(name="fn")
        def fn():
            return 42

        fn()
        spans = exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs["bud.track.output"] == "42"

    def test_captures_dict_keys(self, traced_setup):
        exporter = traced_setup

        @track(name="fn")
        def fn():
            return {"a": 1, "b": 2}

        fn()
        spans = exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs["bud.track.output.a"] == "1"
        assert attrs["bud.track.output.b"] == "2"

    def test_capture_output_false(self, traced_setup):
        exporter = traced_setup

        @track(name="fn", capture_output=False)
        def fn():
            return 42

        fn()
        spans = exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert "bud.track.output" not in attrs

    def test_dict_captures_all_keys(self, traced_setup):
        """Output capture is all-or-nothing — no key-level filtering."""
        exporter = traced_setup

        @track(name="fn")
        def fn():
            return {"a": 1, "b": 2, "c": 3}

        fn()
        spans = exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs["bud.track.output.a"] == "1"
        assert attrs["bud.track.output.b"] == "2"
        assert attrs["bud.track.output.c"] == "3"


# ---------------------------------------------------------------------------
# Type and attributes tests
# ---------------------------------------------------------------------------


class TestTrackTypeAndAttributes:
    def test_type_attribute(self, traced_setup):
        exporter = traced_setup

        @track(name="fn", type="llm")
        def fn():
            return 1

        fn()
        spans = exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs["bud.track.type"] == "llm"

    def test_static_attributes(self, traced_setup):
        exporter = traced_setup

        @track(name="fn", attributes={"env": "test", "version": "1.0"})
        def fn():
            return 1

        fn()
        spans = exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs["env"] == "test"
        assert attrs["version"] == "1.0"

    def test_no_type_no_attribute(self, traced_setup):
        exporter = traced_setup

        @track(name="fn")
        def fn():
            return 1

        fn()
        spans = exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert "bud.track.type" not in attrs


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------


class TestTrackErrorHandling:
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

        assert span.status.status_code == StatusCode.ERROR

        events = span.events
        assert len(events) >= 1
        assert any(e.name == "exception" for e in events)

    def test_error_status_message(self, traced_setup):
        exporter = traced_setup

        @track(name="failing")
        def failing():
            raise RuntimeError("something broke")

        with pytest.raises(RuntimeError):
            failing()

        spans = exporter.get_finished_spans()
        span = spans[0]
        assert "something broke" in span.status.description


# ---------------------------------------------------------------------------
# Generator tests
# ---------------------------------------------------------------------------


class TestTrackGenerators:
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

    def test_sync_generator_mid_error(self, traced_setup):
        exporter = traced_setup

        @track(name="gen")
        def gen():
            yield 1
            yield 2
            raise ValueError("mid-gen error")

        with pytest.raises(ValueError, match="mid-gen error"):
            list(gen())

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        span = spans[0]
        assert span.status.status_code == StatusCode.ERROR

    def test_async_generator_yield_count(self, traced_setup):
        exporter = traced_setup

        @track(name="async-gen")
        async def gen():
            yield 1
            yield 2
            yield 3

        async def collect():
            return [item async for item in gen()]

        result = asyncio.run(collect())
        assert result == [1, 2, 3]

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert dict(spans[0].attributes)["bud.track.yield_count"] == 3

    def test_generator_output_capture_default(self, traced_setup):
        """Default capture_output=True now records aggregated output."""
        exporter = traced_setup

        @track(name="gen")
        def gen():
            yield 1
            yield 2

        list(gen())
        attrs = dict(exporter.get_finished_spans()[0].attributes)
        assert attrs["bud.track.output"] == "[1, 2]"
        assert attrs["bud.track.generator_completed"] is True

    def test_sync_generator_string_output_joined(self, traced_setup):
        exporter = traced_setup

        @track(name="gen")
        def gen():
            yield "Hello"
            yield " "
            yield "world"

        list(gen())
        attrs = dict(exporter.get_finished_spans()[0].attributes)
        assert attrs["bud.track.output"] == "'Hello world'"
        assert attrs["bud.track.yield_count"] == 3

    def test_sync_generator_mixed_types_output(self, traced_setup):
        exporter = traced_setup

        @track(name="gen")
        def gen():
            yield 1
            yield "two"
            yield 3

        list(gen())
        attrs = dict(exporter.get_finished_spans()[0].attributes)
        assert attrs["bud.track.output"] == "[1, 'two', 3]"

    def test_sync_generator_capture_output_false(self, traced_setup):
        exporter = traced_setup

        @track(name="gen", capture_output=False)
        def gen():
            yield 1
            yield 2

        list(gen())
        attrs = dict(exporter.get_finished_spans()[0].attributes)
        assert "bud.track.output" not in attrs
        assert attrs["bud.track.yield_count"] == 2
        assert attrs["bud.track.generator_completed"] is True

    def test_sync_generator_partial_consumption(self, traced_setup):
        exporter = traced_setup

        @track(name="gen")
        def gen():
            yield "a"
            yield "b"
            yield "c"
            yield "d"

        g = gen()
        collected = []
        for item in g:
            collected.append(item)
            if len(collected) == 2:
                break
        # Close explicitly to ensure span is finished
        g.close()

        assert collected == ["a", "b"]
        attrs = dict(exporter.get_finished_spans()[0].attributes)
        assert attrs["bud.track.yield_count"] == 2
        assert attrs["bud.track.generator_completed"] is False
        assert attrs["bud.track.output"] == "'ab'"

    def test_sync_generator_empty(self, traced_setup):
        exporter = traced_setup

        @track(name="gen")
        def gen():
            return
            yield  # noqa: RET504

        list(gen())
        attrs = dict(exporter.get_finished_spans()[0].attributes)
        assert attrs["bud.track.yield_count"] == 0
        assert attrs["bud.track.generator_completed"] is True
        assert "bud.track.output" not in attrs

    def test_sync_generator_error_records_exception(self, traced_setup):
        exporter = traced_setup

        @track(name="gen")
        def gen():
            yield 1
            raise ValueError("mid-gen")

        with pytest.raises(ValueError, match="mid-gen"):
            list(gen())

        span = exporter.get_finished_spans()[0]
        assert span.status.status_code == StatusCode.ERROR
        # yield_count is NOT set after an exception (raise bypasses attribute-setting)
        attrs = dict(span.attributes)
        assert "bud.track.yield_count" not in attrs

    def test_async_generator_string_output_joined(self, traced_setup):
        exporter = traced_setup

        @track(name="async-gen")
        async def gen():
            yield "Hello"
            yield " "
            yield "world"

        async def collect():
            return [item async for item in gen()]

        result = asyncio.run(collect())
        assert result == ["Hello", " ", "world"]
        attrs = dict(exporter.get_finished_spans()[0].attributes)
        assert attrs["bud.track.output"] == "'Hello world'"
        assert attrs["bud.track.yield_count"] == 3

    def test_async_generator_partial_consumption(self, traced_setup):
        exporter = traced_setup

        @track(name="async-gen")
        async def gen():
            yield "x"
            yield "y"
            yield "z"

        async def partial():
            collected = []
            async for item in gen():
                collected.append(item)
                if len(collected) == 1:
                    break
            return collected

        result = asyncio.run(partial())
        assert result == ["x"]
        attrs = dict(exporter.get_finished_spans()[0].attributes)
        assert attrs["bud.track.yield_count"] == 1
        assert attrs["bud.track.generator_completed"] is False
        assert attrs["bud.track.output"] == "'x'"

    def test_async_generator_capture_output_false(self, traced_setup):
        exporter = traced_setup

        @track(name="async-gen", capture_output=False)
        async def gen():
            yield 1
            yield 2

        async def collect():
            return [item async for item in gen()]

        asyncio.run(collect())
        attrs = dict(exporter.get_finished_spans()[0].attributes)
        assert "bud.track.output" not in attrs
        assert attrs["bud.track.yield_count"] == 2

    def test_sync_generator_output_truncated(self, traced_setup):
        exporter = traced_setup

        @track(name="gen")
        def gen():
            yield "x" * 5000

        list(gen())
        attrs = dict(exporter.get_finished_spans()[0].attributes)
        output = attrs["bud.track.output"]
        assert len(output) == 1000
        assert output.endswith("...")


# ---------------------------------------------------------------------------
# _try_aggregate_generator unit tests
# ---------------------------------------------------------------------------


class TestTryAggregateGenerator:
    def test_custom_aggregator(self):
        agg = lambda items: {"total": sum(items)}  # noqa: E731
        result = _try_aggregate_generator([1, 2, 3], agg)
        assert result == "{'total': 6}"

    def test_none_uses_builtin(self):
        result = _try_aggregate_generator(["a", "b"], None)
        assert result == "'ab'"

    def test_aggregator_error_falls_back(self):
        def bad_agg(items):  # noqa: ARG001
            raise RuntimeError("boom")

        result = _try_aggregate_generator([1, 2], bad_agg)
        # Falls back to _safe_repr(str(items)) → repr("[1, 2]") → "'[1, 2]'"
        assert result == "'[1, 2]'"

    def test_none_builtin_with_mixed_types(self):
        result = _try_aggregate_generator([1, "two"], None)
        assert result == "[1, 'two']"

    def test_none_builtin_with_empty(self):
        result = _try_aggregate_generator([], None)
        assert result == "[]"


# ---------------------------------------------------------------------------
# generations_aggregator integration tests
# ---------------------------------------------------------------------------


class TestGenerationsAggregator:
    def test_custom_aggregator_sync(self, traced_setup):
        exporter = traced_setup

        def sum_agg(items):
            return {"total": sum(items)}

        @track(name="gen", generations_aggregator=sum_agg)
        def gen():
            yield 1
            yield 2
            yield 3

        result = list(gen())
        assert result == [1, 2, 3]
        attrs = dict(exporter.get_finished_spans()[0].attributes)
        assert attrs["bud.track.output"] == "{'total': 6}"

    def test_custom_aggregator_async(self, traced_setup):
        exporter = traced_setup

        def join_upper(items):
            return "".join(items).upper()

        @track(name="async-gen", generations_aggregator=join_upper)
        async def gen():
            yield "hello"
            yield " "
            yield "world"

        async def collect():
            return [item async for item in gen()]

        result = asyncio.run(collect())
        assert result == ["hello", " ", "world"]
        attrs = dict(exporter.get_finished_spans()[0].attributes)
        assert attrs["bud.track.output"] == "'HELLO WORLD'"

    def test_aggregator_error_falls_back(self, traced_setup):
        exporter = traced_setup

        def bad_agg(items):  # noqa: ARG001
            raise RuntimeError("boom")

        @track(name="gen", generations_aggregator=bad_agg)
        def gen():
            yield 1
            yield 2

        list(gen())
        attrs = dict(exporter.get_finished_spans()[0].attributes)
        # Falls back to _safe_repr(str(items)) → repr("[1, 2]") → "'[1, 2]'"
        assert attrs["bud.track.output"] == "'[1, 2]'"

    def test_no_aggregator_uses_builtin(self, traced_setup):
        """Default behavior preserved when generations_aggregator is None."""
        exporter = traced_setup

        @track(name="gen")
        def gen():
            yield "Hello"
            yield " "
            yield "world"

        list(gen())
        attrs = dict(exporter.get_finished_spans()[0].attributes)
        assert attrs["bud.track.output"] == "'Hello world'"

    def test_aggregator_none_equivalent(self, traced_setup):
        """Explicit None = builtin default."""
        exporter = traced_setup

        @track(name="gen", generations_aggregator=None)
        def gen():
            yield "a"
            yield "b"

        list(gen())
        attrs = dict(exporter.get_finished_spans()[0].attributes)
        assert attrs["bud.track.output"] == "'ab'"
