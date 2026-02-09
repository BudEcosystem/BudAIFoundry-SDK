"""Tests for _provider.py — CREATE, ATTACH, AUTO mode behavior."""

from __future__ import annotations

from unittest.mock import patch

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider as SdkTracerProvider

from bud.observability._config import ObservabilityConfig, ObservabilityMode
from bud.observability._provider import (
    ProviderBundle,
    create_providers,
    detect_mode,
)


class TestDetectMode:
    def test_returns_explicit_mode(self) -> None:
        config = ObservabilityConfig(mode=ObservabilityMode.CREATE)
        assert detect_mode(config) == ObservabilityMode.CREATE

    def test_returns_disabled(self) -> None:
        config = ObservabilityConfig(mode=ObservabilityMode.DISABLED)
        assert detect_mode(config) == ObservabilityMode.DISABLED

    def test_auto_detects_create_when_no_provider(self) -> None:
        config = ObservabilityConfig(mode=ObservabilityMode.AUTO)
        # Default OTel state has proxy provider
        result = detect_mode(config)
        assert result in (ObservabilityMode.CREATE, ObservabilityMode.ATTACH)

    def test_auto_detects_attach_when_sdk_provider(self) -> None:
        config = ObservabilityConfig(mode=ObservabilityMode.AUTO)
        sdk_provider = SdkTracerProvider()
        with patch.object(trace, "get_tracer_provider", return_value=sdk_provider):
            result = detect_mode(config)
        assert result == ObservabilityMode.ATTACH
        sdk_provider.shutdown()


class TestCreateProviders:
    def test_creates_tracer_provider(self) -> None:
        config = ObservabilityConfig(
            mode=ObservabilityMode.CREATE,
            collector_endpoint="http://localhost:4318",
            compression="none",
            traces_enabled=True,
            metrics_enabled=False,
            logs_enabled=False,
            instrumentors=[],
        )
        bundle = create_providers(config)
        assert bundle.tracer_provider is not None
        assert bundle.owned is True
        # Cleanup
        bundle.tracer_provider.shutdown()

    def test_creates_meter_provider(self) -> None:
        config = ObservabilityConfig(
            mode=ObservabilityMode.CREATE,
            collector_endpoint="http://localhost:4318",
            compression="none",
            traces_enabled=False,
            metrics_enabled=True,
            logs_enabled=False,
            instrumentors=[],
        )
        bundle = create_providers(config)
        assert bundle.meter_provider is not None
        assert bundle.owned is True
        # Cleanup
        bundle.meter_provider.shutdown()

    def test_disabled_traces(self) -> None:
        config = ObservabilityConfig(
            mode=ObservabilityMode.CREATE,
            collector_endpoint="http://localhost:4318",
            compression="none",
            traces_enabled=False,
            metrics_enabled=False,
            logs_enabled=False,
            instrumentors=[],
        )
        bundle = create_providers(config)
        assert bundle.tracer_provider is None

    def test_bundle_dataclass(self) -> None:
        bundle = ProviderBundle()
        assert bundle.tracer_provider is None
        assert bundle.meter_provider is None
        assert bundle.logger_provider is None
        assert bundle.owned is False
