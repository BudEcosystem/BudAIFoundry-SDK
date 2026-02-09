"""Tests for _logging.py — Python log to OTel log bridge."""

from __future__ import annotations

import logging

from bud.observability._config import ObservabilityConfig
from bud.observability._logging import setup_log_bridge, setup_log_provider


class TestSetupLogProvider:
    def test_creates_logger_provider(self) -> None:
        config = ObservabilityConfig(
            collector_endpoint="http://localhost:4318",
            compression="none",
        )
        provider = setup_log_provider(config)
        assert provider is not None
        # Cleanup
        provider.shutdown()


class TestSetupLogBridge:
    def test_attaches_handler_to_root_logger(self) -> None:
        config = ObservabilityConfig(
            collector_endpoint="http://localhost:4318",
            compression="none",
        )
        provider = setup_log_provider(config)
        root = logging.getLogger()
        initial_count = len(root.handlers)

        setup_log_bridge(provider, min_level="WARNING")

        assert len(root.handlers) == initial_count + 1

        # Cleanup: remove the handler we added
        root.handlers = root.handlers[:initial_count]
        provider.shutdown()

    def test_custom_log_level(self) -> None:
        config = ObservabilityConfig(
            collector_endpoint="http://localhost:4318",
            compression="none",
        )
        provider = setup_log_provider(config)
        root = logging.getLogger()
        initial_count = len(root.handlers)

        setup_log_bridge(provider, min_level="ERROR")

        handler = root.handlers[-1]
        assert handler.level == logging.ERROR

        # Cleanup
        root.handlers = root.handlers[:initial_count]
        provider.shutdown()
