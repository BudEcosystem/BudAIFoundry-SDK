"""Tests for _noop.py — No-op safety when OTel missing."""

from __future__ import annotations

from bud.observability._noop import (
    _check_otel_available,
    _NoOpCounter,
    _NoOpHistogram,
    _NoOpMeter,
    _NoOpSpan,
    _NoOpTracer,
    _NoOpUpDownCounter,
)


class TestCheckOtelAvailable:
    def test_returns_true_when_installed(self) -> None:
        assert _check_otel_available() is True


class TestNoOpSpan:
    def test_all_methods_are_safe(self) -> None:
        span = _NoOpSpan()
        span.end()
        span.set_attribute("key", "value")
        span.set_attributes({"key": "value"})
        span.add_event("test")
        span.set_status("OK")
        span.record_exception(RuntimeError("test"))
        span.update_name("new_name")
        assert span.is_recording() is False
        assert span.get_span_context() is None

    def test_context_manager(self) -> None:
        span = _NoOpSpan()
        with span as s:
            assert s is span


class TestNoOpTracer:
    def test_start_span_returns_noop(self) -> None:
        tracer = _NoOpTracer()
        span = tracer.start_span("test")
        assert isinstance(span, _NoOpSpan)

    def test_start_as_current_span_returns_noop(self) -> None:
        tracer = _NoOpTracer()
        with tracer.start_as_current_span("test") as span:
            assert isinstance(span, _NoOpSpan)


class TestNoOpMeter:
    def test_create_counter(self) -> None:
        meter = _NoOpMeter()
        counter = meter.create_counter("test")
        assert isinstance(counter, _NoOpCounter)
        counter.add(1)  # Should not raise

    def test_create_histogram(self) -> None:
        meter = _NoOpMeter()
        histogram = meter.create_histogram("test")
        assert isinstance(histogram, _NoOpHistogram)
        histogram.record(1.5)  # Should not raise

    def test_create_up_down_counter(self) -> None:
        meter = _NoOpMeter()
        counter = meter.create_up_down_counter("test")
        assert isinstance(counter, _NoOpUpDownCounter)
        counter.add(-1)  # Should not raise
