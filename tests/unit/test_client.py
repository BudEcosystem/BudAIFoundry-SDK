"""Tests for BudClient."""

from __future__ import annotations

import pytest

from bud.auth import APIKeyAuth
from bud.client import BudClient


def test_client_requires_auth() -> None:
    """Test that client raises error without any authentication."""
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
