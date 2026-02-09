"""Core provider strategy for CREATE, ATTACH, AUTO, and INTERNAL modes.

Implements the provider decision tree:
- CREATE: SDK creates and owns all providers, sets globals
- ATTACH: SDK adds processors to existing providers
- AUTO: Detects existing providers, falls back to CREATE
- INTERNAL: CREATE + aggressive batching + no auth
- DISABLED: No-op
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from bud.observability._config import ObservabilityConfig, ObservabilityMode

logger = logging.getLogger("bud.observability")


@dataclass
class ProviderBundle:
    """Container for all three OTel providers."""

    tracer_provider: Any = None
    meter_provider: Any = None
    logger_provider: Any = None
    owned: bool = False  # Did we create these providers?


def detect_mode(config: ObservabilityConfig) -> ObservabilityMode:
    """Implement AUTO mode detection.

    If an existing SDK TracerProvider is registered globally, use ATTACH.
    Otherwise, use CREATE.
    """
    if config.mode != ObservabilityMode.AUTO:
        return config.mode

    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider as SdkTracerProvider

    current = trace.get_tracer_provider()
    if isinstance(current, SdkTracerProvider):
        return ObservabilityMode.ATTACH
    return ObservabilityMode.CREATE


def create_providers(config: ObservabilityConfig) -> ProviderBundle:
    """Implement CREATE mode: create new providers and set globals.

    1. Build Resource
    2. Create TracerProvider with BaggageSpanProcessor + BatchSpanProcessor
    3. Create MeterProvider with PeriodicExportingMetricReader
    4. Create LoggerProvider with BatchLogRecordProcessor
    5. Set global providers and propagator
    """
    from opentelemetry import metrics, trace
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    from bud._version import __version__
    from bud.observability._attributes import SDK_LANGUAGE_VALUE, SDK_VERSION
    from bud.observability._baggage import BaggageSpanProcessor
    from bud.observability._exporter import create_metric_exporter, create_trace_exporter
    from bud.observability._propagation import setup_propagator

    # Build resource
    resource_attrs = {
        "service.name": config.service_name,
        SDK_VERSION: __version__,
        "bud.sdk.language": SDK_LANGUAGE_VALUE,
    }
    if config.service_version:
        resource_attrs["service.version"] = config.service_version
    if config.deployment_environment:
        resource_attrs["deployment.environment"] = config.deployment_environment
    resource_attrs.update(config.resource_attributes)
    resource = Resource.create(resource_attrs)

    bundle = ProviderBundle(owned=True)

    # Traces
    if config.traces_enabled:
        tracer_provider = TracerProvider(resource=resource)
        # BaggageSpanProcessor must be first
        tracer_provider.add_span_processor(BaggageSpanProcessor())
        # Authenticated OTLP exporter
        trace_exporter = create_trace_exporter(config)
        tracer_provider.add_span_processor(
            BatchSpanProcessor(
                trace_exporter,
                max_queue_size=config.batch_max_queue_size,
                max_export_batch_size=config.batch_max_export_size,
                schedule_delay_millis=config.batch_schedule_delay_ms,
                export_timeout_millis=config.export_timeout_ms,
            )
        )
        trace.set_tracer_provider(tracer_provider)
        bundle.tracer_provider = tracer_provider

    # Metrics
    if config.metrics_enabled:
        metric_exporter = create_metric_exporter(config)
        reader = PeriodicExportingMetricReader(
            metric_exporter,
            export_interval_millis=config.metrics_export_interval_ms,
        )
        meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
        metrics.set_meter_provider(meter_provider)
        bundle.meter_provider = meter_provider

    # Logs
    if config.logs_enabled:
        try:
            from bud.observability._logging import setup_log_bridge, setup_log_provider

            log_provider = setup_log_provider(config, resource=resource)
            setup_log_bridge(log_provider, config.log_level)
            bundle.logger_provider = log_provider
        except Exception:
            logger.debug("Log provider setup failed, skipping", exc_info=True)

    # Propagator
    setup_propagator()

    return bundle


def attach_to_providers(config: ObservabilityConfig) -> ProviderBundle:
    """Implement ATTACH mode: add processors to existing providers.

    Does NOT override global propagator or replace existing providers.
    Falls back to CREATE if existing provider is proxy/noop.
    """
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider as SdkTracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    from bud.observability._baggage import BaggageSpanProcessor
    from bud.observability._exporter import create_trace_exporter

    current_tp = config.tracer_provider or trace.get_tracer_provider()
    bundle = ProviderBundle(owned=False)

    if isinstance(current_tp, SdkTracerProvider):
        # Add our processors to existing provider
        current_tp.add_span_processor(BaggageSpanProcessor())
        trace_exporter = create_trace_exporter(config)
        current_tp.add_span_processor(
            BatchSpanProcessor(
                trace_exporter,
                max_queue_size=config.batch_max_queue_size,
                max_export_batch_size=config.batch_max_export_size,
                schedule_delay_millis=config.batch_schedule_delay_ms,
                export_timeout_millis=config.export_timeout_ms,
            )
        )
        bundle.tracer_provider = current_tp
    else:
        # Proxy/noop provider — fall back to CREATE
        logger.info("Existing provider is proxy/noop, falling back to CREATE mode")
        return create_providers(config)

    # For meter/logger providers, use existing if provided or create new
    if config.meter_provider:
        bundle.meter_provider = config.meter_provider
    if config.logger_provider:
        bundle.logger_provider = config.logger_provider

    return bundle
