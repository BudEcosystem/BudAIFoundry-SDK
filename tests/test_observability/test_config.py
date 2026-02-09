"""Tests for _config.py — Config from args, env vars, defaults."""

from __future__ import annotations

import os
from unittest.mock import patch

from bud.observability._config import ObservabilityConfig, ObservabilityMode


class TestObservabilityMode:
    def test_mode_values(self) -> None:
        assert ObservabilityMode.AUTO == "auto"
        assert ObservabilityMode.CREATE == "create"
        assert ObservabilityMode.ATTACH == "attach"
        assert ObservabilityMode.INTERNAL == "internal"
        assert ObservabilityMode.DISABLED == "disabled"

    def test_mode_from_string(self) -> None:
        assert ObservabilityMode("auto") == ObservabilityMode.AUTO
        assert ObservabilityMode("create") == ObservabilityMode.CREATE


class TestObservabilityConfig:
    def test_defaults(self) -> None:
        config = ObservabilityConfig()
        assert config.mode == ObservabilityMode.AUTO
        assert config.api_key is None
        assert config.collector_endpoint == "https://otel.bud.studio:4318"
        assert config.service_name == "bud-sdk-client"
        assert config.enabled is True
        assert config.traces_enabled is True
        assert config.metrics_enabled is True
        assert config.logs_enabled is True
        assert config.compression == "gzip"
        assert config.instrumentors == ["httpx"]
        assert config.batch_max_queue_size == 2048
        assert config.batch_max_export_size == 512
        assert config.batch_schedule_delay_ms == 5000
        assert config.metrics_export_interval_ms == 60000
        assert config.log_level == "WARNING"

    def test_custom_values(self) -> None:
        config = ObservabilityConfig(
            mode=ObservabilityMode.CREATE,
            api_key="test-key",
            service_name="my-service",
            collector_endpoint="http://localhost:4318",
        )
        assert config.mode == ObservabilityMode.CREATE
        assert config.api_key == "test-key"
        assert config.service_name == "my-service"
        assert config.collector_endpoint == "http://localhost:4318"

    def test_resolve_from_env_bud_vars(self) -> None:
        env = {
            "BUD_OTEL_API_KEY": "env-key",
            "BUD_OTEL_ENDPOINT": "http://env:4318",
            "BUD_OTEL_SERVICE_NAME": "env-service",
            "BUD_OTEL_MODE": "create",
            "BUD_OTEL_ENABLED": "true",
        }
        with patch.dict(os.environ, env, clear=False):
            config = ObservabilityConfig._resolve_from_env()
        assert config.api_key == "env-key"
        assert config.collector_endpoint == "http://env:4318"
        assert config.service_name == "env-service"
        assert config.mode == ObservabilityMode.CREATE
        assert config.enabled is True

    def test_resolve_from_env_otel_fallback(self) -> None:
        env = {
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://otel:4318",
            "OTEL_SERVICE_NAME": "otel-service",
        }
        with patch.dict(os.environ, env, clear=False):
            # Remove any BUD_OTEL_ vars that might exist
            for key in list(os.environ):
                if key.startswith("BUD_OTEL_"):
                    del os.environ[key]
            config = ObservabilityConfig._resolve_from_env()
        assert config.collector_endpoint == "http://otel:4318"
        assert config.service_name == "otel-service"

    def test_resolve_from_env_disabled(self) -> None:
        with patch.dict(os.environ, {"BUD_OTEL_ENABLED": "false"}, clear=False):
            config = ObservabilityConfig._resolve_from_env()
        assert config.enabled is False

    def test_apply_internal_defaults(self) -> None:
        config = ObservabilityConfig(mode=ObservabilityMode.INTERNAL)
        config._apply_internal_defaults()
        assert config.batch_max_queue_size == 4096
        assert config.batch_max_export_size == 1024
        assert config.batch_schedule_delay_ms == 2000
        assert config.metrics_export_interval_ms == 30000
        assert config.compression == "none"

    def test_apply_internal_defaults_noop_for_other_modes(self) -> None:
        config = ObservabilityConfig(mode=ObservabilityMode.CREATE)
        config._apply_internal_defaults()
        assert config.batch_max_queue_size == 2048  # unchanged
