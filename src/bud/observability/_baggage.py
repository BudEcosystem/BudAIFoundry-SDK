"""BaggageSpanProcessor — copies W3C Baggage entries to span attributes.

Extracted from budprompt's shared/baggage_processor.py as the single source of truth.
This processor runs on every span start and copies bud.* baggage keys
from the OTel context to span attributes, enabling per-project filtering.
"""

from __future__ import annotations

from opentelemetry import baggage, context
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor

from bud.observability._attributes import BAGGAGE_KEYS


class BaggageSpanProcessor(SpanProcessor):
    """SpanProcessor that copies bud.* W3C Baggage entries to span attributes on start."""

    def on_start(self, span: Span, parent_context: context.Context | None = None) -> None:
        ctx = parent_context if parent_context is not None else context.get_current()
        for key in BAGGAGE_KEYS:
            value = baggage.get_baggage(key, context=ctx)
            if value is not None:
                span.set_attribute(key, str(value))

    def on_end(self, span: ReadableSpan) -> None:  # noqa: ARG002
        pass

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:  # noqa: ARG002
        return True
