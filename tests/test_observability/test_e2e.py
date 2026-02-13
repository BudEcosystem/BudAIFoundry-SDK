"""End-to-end test — Full configure → span → export cycle with InMemorySpanExporter."""

from __future__ import annotations

from opentelemetry import baggage, context
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from bud.observability._attributes import PROJECT_ID, PROMPT_ID
from bud.observability._baggage import BaggageSpanProcessor


class TestE2ETraceFlow:
    def test_full_configure_span_export_cycle(self) -> None:
        """Test: configure → create span → BaggageProcessor copies attrs → export."""
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(BaggageSpanProcessor())
        provider.add_span_processor(SimpleSpanProcessor(exporter))

        tracer = provider.get_tracer("test")

        # Simulate gateway setting baggage
        ctx = context.get_current()
        ctx = baggage.set_baggage(PROJECT_ID, "proj-e2e", context=ctx)
        ctx = baggage.set_baggage(PROMPT_ID, "prompt-e2e", context=ctx)
        token = context.attach(ctx)

        try:
            with tracer.start_as_current_span("inference.request") as span:
                span.set_attribute("custom.key", "value")
        finally:
            context.detach(token)

        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        exported_span = spans[0]
        attrs = dict(exported_span.attributes)
        assert attrs[PROJECT_ID] == "proj-e2e"
        assert attrs[PROMPT_ID] == "prompt-e2e"
        assert attrs["custom.key"] == "value"
        assert exported_span.name == "inference.request"

        # Cleanup
        provider.shutdown()

    def test_span_without_baggage(self) -> None:
        """Test: spans work fine even without baggage set."""
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(BaggageSpanProcessor())
        provider.add_span_processor(SimpleSpanProcessor(exporter))

        tracer = provider.get_tracer("test")
        with tracer.start_as_current_span("no-baggage-span"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        # No bud.* attributes should be set
        attrs = dict(spans[0].attributes)
        assert PROJECT_ID not in attrs

        provider.shutdown()

    def test_nested_spans_inherit_baggage(self) -> None:
        """Test: child spans also get baggage attributes."""
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(BaggageSpanProcessor())
        provider.add_span_processor(SimpleSpanProcessor(exporter))

        tracer = provider.get_tracer("test")

        ctx = context.get_current()
        ctx = baggage.set_baggage(PROJECT_ID, "proj-nested", context=ctx)
        token = context.attach(ctx)

        try:
            with tracer.start_as_current_span("parent"), tracer.start_as_current_span("child"):
                pass
        finally:
            context.detach(token)

        spans = exporter.get_finished_spans()
        assert len(spans) == 2
        for s in spans:
            assert dict(s.attributes).get(PROJECT_ID) == "proj-nested"

        provider.shutdown()
