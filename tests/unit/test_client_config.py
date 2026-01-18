"""Tests for BudClient config file auth."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from bud.auth import APIKeyAuth, DaprAuth, JWTAuth
from bud.client import BudClient


class TestBudClientConfigAuth:
    """Test BudClient auth from config file."""

    def test_client_loads_api_key_from_config(self, tmp_path: Path) -> None:
        """Client should load API key from config file."""
        config_file = tmp_path / "config.toml"
        config_file.write_text('api_key = "config-api-key"\n')

        with (
            patch("bud._config.CONFIG_FILE", config_file),
            patch.dict(os.environ, {}, clear=True),
        ):
            client = BudClient(base_url="https://api.example.com")

            assert isinstance(client._auth, APIKeyAuth)
            assert client._auth.api_key == "config-api-key"

    def test_client_loads_dapr_from_config(self, tmp_path: Path) -> None:
        """Client should load Dapr token from config file."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            '[auth]\ntype = "dapr"\ntoken = "config-dapr-token"\nuser_id = "config-user"\n'
        )

        with (
            patch("bud._config.CONFIG_FILE", config_file),
            patch.dict(os.environ, {}, clear=True),
        ):
            client = BudClient(base_url="https://api.example.com")

            assert isinstance(client._auth, DaprAuth)
            assert client._auth.token == "config-dapr-token"
            assert client._auth.user_id == "config-user"

    def test_client_loads_jwt_from_config(self, tmp_path: Path) -> None:
        """Client should load JWT credentials from config file."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            '[auth]\ntype = "jwt"\nemail = "config@example.com"\npassword = "config-secret"\n'
        )

        with (
            patch("bud._config.CONFIG_FILE", config_file),
            patch.dict(os.environ, {}, clear=True),
        ):
            client = BudClient(base_url="https://api.example.com")

            assert isinstance(client._auth, JWTAuth)
            assert client._auth.email == "config@example.com"
            assert client._auth.password == "config-secret"

    def test_client_explicit_overrides_config(self, tmp_path: Path) -> None:
        """Explicit parameters should override config file auth."""
        config_file = tmp_path / "config.toml"
        config_file.write_text('api_key = "config-api-key"\n')

        with (
            patch("bud._config.CONFIG_FILE", config_file),
            patch.dict(os.environ, {}, clear=True),
        ):
            client = BudClient(
                api_key="explicit-api-key",
                base_url="https://api.example.com",
            )

            assert isinstance(client._auth, APIKeyAuth)
            assert client._auth.api_key == "explicit-api-key"

    def test_client_env_overrides_config(self, tmp_path: Path) -> None:
        """Environment variables should override config file auth."""
        config_file = tmp_path / "config.toml"
        config_file.write_text('api_key = "config-api-key"\n')

        with (
            patch("bud._config.CONFIG_FILE", config_file),
            patch.dict(os.environ, {"BUD_API_KEY": "env-api-key"}, clear=True),
        ):
            client = BudClient(base_url="https://api.example.com")

            assert isinstance(client._auth, APIKeyAuth)
            assert client._auth.api_key == "env-api-key"

    def test_client_config_auth_priority(self, tmp_path: Path) -> None:
        """Auth from config should follow priority: api_key > dapr > jwt."""
        # Config with both api_key and auth section
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            'api_key = "config-api-key"\n'
            '[auth]\ntype = "jwt"\nemail = "user@example.com"\npassword = "secret"\n'
        )

        with (
            patch("bud._config.CONFIG_FILE", config_file),
            patch.dict(os.environ, {}, clear=True),
        ):
            client = BudClient(base_url="https://api.example.com")

            # api_key should take priority
            assert isinstance(client._auth, APIKeyAuth)
            assert client._auth.api_key == "config-api-key"

    def test_client_config_dapr_without_user_id(self, tmp_path: Path) -> None:
        """Dapr auth from config should work without user_id."""
        config_file = tmp_path / "config.toml"
        config_file.write_text('[auth]\ntype = "dapr"\ntoken = "dapr-token"\n')

        with (
            patch("bud._config.CONFIG_FILE", config_file),
            patch.dict(os.environ, {}, clear=True),
        ):
            client = BudClient(base_url="https://api.example.com")

            assert isinstance(client._auth, DaprAuth)
            assert client._auth.token == "dapr-token"
            assert client._auth.user_id is None

    def test_client_no_config_file_still_requires_auth(self, tmp_path: Path) -> None:
        """Client should still require auth if no config file exists."""
        config_file = tmp_path / "nonexistent.toml"

        with (
            patch("bud._config.CONFIG_FILE", config_file),
            patch.dict(os.environ, {}, clear=True),
            patch.object(BudClient, "_load_stored_tokens", return_value=None),
        ):
            with pytest.raises(ValueError, match="No authentication"):
                BudClient(base_url="https://api.example.com")
