"""Tests for _baggage.py — BaggageSpanProcessor key copying."""

from __future__ import annotations

from unittest.mock import MagicMock

from opentelemetry import baggage, context

from bud.observability._attributes import BAGGAGE_KEYS, ENDPOINT_ID, PROJECT_ID, PROMPT_ID
from bud.observability._baggage import BaggageSpanProcessor


class TestBaggageSpanProcessor:
    def test_copies_baggage_to_span_attributes(self) -> None:
        processor = BaggageSpanProcessor()
        span = MagicMock()

        # Set up context with baggage
        ctx = context.get_current()
        ctx = baggage.set_baggage(PROJECT_ID, "proj-123", context=ctx)
        ctx = baggage.set_baggage(PROMPT_ID, "prompt-456", context=ctx)

        processor.on_start(span, parent_context=ctx)

        span.set_attribute.assert_any_call(PROJECT_ID, "proj-123")
        span.set_attribute.assert_any_call(PROMPT_ID, "prompt-456")

    def test_skips_empty_baggage(self) -> None:
        processor = BaggageSpanProcessor()
        span = MagicMock()

        ctx = context.get_current()
        processor.on_start(span, parent_context=ctx)

        span.set_attribute.assert_not_called()

    def test_copies_all_keys(self) -> None:
        processor = BaggageSpanProcessor()
        span = MagicMock()

        ctx = context.get_current()
        for key in BAGGAGE_KEYS:
            ctx = baggage.set_baggage(key, f"value-{key}", context=ctx)

        processor.on_start(span, parent_context=ctx)

        assert span.set_attribute.call_count == len(BAGGAGE_KEYS)
        for key in BAGGAGE_KEYS:
            span.set_attribute.assert_any_call(key, f"value-{key}")

    def test_uses_current_context_when_none(self) -> None:
        processor = BaggageSpanProcessor()
        span = MagicMock()

        # Set baggage on current context
        ctx = baggage.set_baggage(ENDPOINT_ID, "ep-789")
        token = context.attach(ctx)
        try:
            processor.on_start(span, parent_context=None)
            span.set_attribute.assert_any_call(ENDPOINT_ID, "ep-789")
        finally:
            context.detach(token)

    def test_on_end_is_noop(self) -> None:
        processor = BaggageSpanProcessor()
        processor.on_end(MagicMock())  # Should not raise

    def test_shutdown_is_noop(self) -> None:
        processor = BaggageSpanProcessor()
        processor.shutdown()  # Should not raise

    def test_force_flush_returns_true(self) -> None:
        processor = BaggageSpanProcessor()
        assert processor.force_flush() is True
