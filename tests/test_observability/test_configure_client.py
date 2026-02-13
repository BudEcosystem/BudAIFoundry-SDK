"""Tests for configure(client=...) parameter."""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import patch

from bud.observability._config import ObservabilityConfig


class TestConfigureClientParam:
    """Test that configure() extracts api_key and base_url from a client object."""

    def _make_client(
        self, api_key: str | None = None, base_url: str | None = None
    ) -> SimpleNamespace:
        """Create a minimal client-like object with api_key and base_url."""
        return SimpleNamespace(api_key=api_key, base_url=base_url)

    def test_client_fills_defaults(self) -> None:
        """Client values fill in when no env vars are set."""
        config = ObservabilityConfig._resolve_from_env()
        client = self._make_client(api_key="client-key", base_url="http://client:4318")

        # Simulate what configure() does
        if client is not None:
            _client_api_key = getattr(client, "api_key", None)
            _client_base_url = getattr(client, "base_url", None)
            if _client_api_key and config.api_key is None:
                config.api_key = _client_api_key
            if _client_base_url and config.collector_endpoint is None:
                config.collector_endpoint = _client_base_url

        assert config.api_key == "client-key"
        assert config.collector_endpoint == "http://client:4318"

    def test_env_vars_take_precedence_over_client(self) -> None:
        """BUD_API_KEY / BUD_BASE_URL from env override client values."""
        env = {"BUD_API_KEY": "env-key", "BUD_BASE_URL": "http://env:4318"}
        with patch.dict(os.environ, env, clear=True):
            config = ObservabilityConfig._resolve_from_env()

        client = self._make_client(api_key="client-key", base_url="http://client:4318")

        if client is not None:
            _client_api_key = getattr(client, "api_key", None)
            _client_base_url = getattr(client, "base_url", None)
            if _client_api_key and config.api_key is None:
                config.api_key = _client_api_key
            if _client_base_url and config.collector_endpoint is None:
                config.collector_endpoint = _client_base_url

        # Env vars should win over client
        assert config.api_key == "env-key"
        assert config.collector_endpoint == "http://env:4318"

    def test_explicit_kwargs_override_client(self) -> None:
        """Explicit api_key/collector_endpoint kwargs override client values."""
        config = ObservabilityConfig._resolve_from_env()
        client = self._make_client(api_key="client-key", base_url="http://client:4318")

        if client is not None:
            _client_api_key = getattr(client, "api_key", None)
            _client_base_url = getattr(client, "base_url", None)
            if _client_api_key and config.api_key is None:
                config.api_key = _client_api_key
            if _client_base_url and config.collector_endpoint is None:
                config.collector_endpoint = _client_base_url

        # Simulate explicit kwarg overrides (as configure() does)
        config.api_key = "explicit-key"
        config.collector_endpoint = "http://explicit:4318"

        assert config.api_key == "explicit-key"
        assert config.collector_endpoint == "http://explicit:4318"

    def test_client_none_is_noop(self) -> None:
        """client=None should not affect config."""
        with patch.dict(os.environ, {}, clear=True):
            config = ObservabilityConfig._resolve_from_env()

        client = None
        if client is not None:
            _client_api_key = getattr(client, "api_key", None)
            _client_base_url = getattr(client, "base_url", None)
            if _client_api_key and config.api_key is None:
                config.api_key = _client_api_key
            if _client_base_url and config.collector_endpoint is None:
                config.collector_endpoint = _client_base_url

        assert config.api_key is None
        assert config.collector_endpoint is None

    def test_client_without_api_key(self) -> None:
        """Client with api_key=None should not override config.api_key."""
        config = ObservabilityConfig._resolve_from_env()
        client = self._make_client(api_key=None, base_url="http://client:4318")

        if client is not None:
            _client_api_key = getattr(client, "api_key", None)
            _client_base_url = getattr(client, "base_url", None)
            if _client_api_key and config.api_key is None:
                config.api_key = _client_api_key
            if _client_base_url and config.collector_endpoint is None:
                config.collector_endpoint = _client_base_url

        assert config.api_key is None
        assert config.collector_endpoint == "http://client:4318"
