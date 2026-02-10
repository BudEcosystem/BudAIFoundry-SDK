"""Tests for BudClient."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from bud.auth import APIKeyAuth, DaprAuth
from bud.client import AsyncBudClient, BudClient


def test_client_requires_auth() -> None:
    """Test that client raises error without any authentication."""
    with patch.object(BudClient, "_load_stored_tokens", return_value=None):
        with pytest.raises(ValueError) as exc_info:
            BudClient(base_url="https://api.example.com")

        assert "No authentication" in str(exc_info.value)


def test_client_with_api_key(api_key: str, base_url: str) -> None:
    """Test client initialization with API key."""
    client = BudClient(api_key=api_key, base_url=base_url)

    assert isinstance(client._auth, APIKeyAuth)
    assert client._auth.api_key == api_key
    assert client._base_url == base_url
    assert client.pipelines is not None
    assert client.executions is not None
    assert client.schedules is not None

    client.close()


def test_client_context_manager(api_key: str, base_url: str) -> None:
    """Test client as context manager."""
    with BudClient(api_key=api_key, base_url=base_url) as client:
        assert isinstance(client._auth, APIKeyAuth)
        assert client._auth.api_key == api_key


def test_client_repr(api_key: str, base_url: str) -> None:
    """Test client string representation."""
    with BudClient(api_key=api_key, base_url=base_url) as client:
        assert base_url in repr(client)


def test_client_base_url_property(api_key: str, base_url: str) -> None:
    """Test that base_url property returns the configured URL."""
    with BudClient(api_key=api_key, base_url=base_url) as client:
        assert client.base_url == base_url


def test_client_api_key_property(api_key: str, base_url: str) -> None:
    """Test that api_key property returns the key for APIKeyAuth."""
    with BudClient(api_key=api_key, base_url=base_url) as client:
        assert client.api_key == api_key


def test_client_api_key_returns_none_for_non_apikey_auth(base_url: str) -> None:
    """Test that api_key property returns None for non-API-key auth (e.g. DaprAuth)."""
    client = BudClient(dapr_token="test-dapr-token", base_url=base_url)
    assert isinstance(client._auth, DaprAuth)
    assert client.api_key is None
    client.close()


def test_async_client_base_url_property(api_key: str, base_url: str) -> None:
    """Test that AsyncBudClient.base_url returns the configured URL."""
    client = AsyncBudClient(api_key=api_key, base_url=base_url)
    assert client.base_url == base_url


def test_async_client_api_key_property(api_key: str, base_url: str) -> None:
    """Test that AsyncBudClient.api_key returns the configured key."""
    client = AsyncBudClient(api_key=api_key, base_url=base_url)
    assert client.api_key == api_key
