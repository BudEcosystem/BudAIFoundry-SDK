"""Tests for ATTACH mode — adds processors to existing provider."""

from __future__ import annotations

from opentelemetry import baggage, context
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from bud.observability._attributes import PROJECT_ID
from bud.observability._config import ObservabilityConfig, ObservabilityMode
from bud.observability._provider import attach_to_providers


class TestAttachMode:
    def test_attach_adds_processors_to_existing(self) -> None:
        """Test: ATTACH mode adds BaggageSpanProcessor to existing SDK TracerProvider."""
        # Pre-existing provider (simulating user's OTel setup)
        existing_exporter = InMemorySpanExporter()
        existing_provider = TracerProvider()
        existing_provider.add_span_processor(SimpleSpanProcessor(existing_exporter))

        config = ObservabilityConfig(
            mode=ObservabilityMode.ATTACH,
            collector_endpoint="http://localhost:4318",
            compression="none",
            tracer_provider=existing_provider,
            metrics_enabled=False,
            logs_enabled=False,
        )

        bundle = attach_to_providers(config)
        assert bundle.tracer_provider is existing_provider

        # Now create a span with baggage — BaggageSpanProcessor should copy it
        tracer = existing_provider.get_tracer("attach-test")
        ctx = context.get_current()
        ctx = baggage.set_baggage(PROJECT_ID, "proj-attach", context=ctx)
        token = context.attach(ctx)

        try:
            with tracer.start_as_current_span("attach-span"):
                pass
        finally:
            context.detach(token)

        spans = existing_exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = dict(spans[0].attributes)
        assert attrs.get(PROJECT_ID) == "proj-attach"

        existing_provider.shutdown()
