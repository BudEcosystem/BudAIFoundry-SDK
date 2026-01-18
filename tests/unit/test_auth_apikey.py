"""Tests for API Key authentication provider."""

from __future__ import annotations

import httpx
import pytest

from bud.auth import APIKeyAuth, AuthProvider


class TestAPIKeyAuth:
    """Test APIKeyAuth authentication provider."""

    def test_api_key_auth_inherits_auth_provider(self) -> None:
        """APIKeyAuth should inherit from AuthProvider."""
        auth = APIKeyAuth(api_key="test-key")
        assert isinstance(auth, AuthProvider)

    def test_api_key_auth_get_headers(self) -> None:
        """get_headers should return Bearer token header."""
        auth = APIKeyAuth(api_key="bud_sk_test123")
        headers = auth.get_headers()

        assert headers == {"Authorization": "Bearer bud_sk_test123"}

    def test_api_key_auth_needs_refresh_always_false(self) -> None:
        """needs_refresh should always return False for API keys."""
        auth = APIKeyAuth(api_key="bud_sk_test123")
        assert auth.needs_refresh() is False

    def test_api_key_auth_is_authenticated(self) -> None:
        """is_authenticated should return True when key is present."""
        auth = APIKeyAuth(api_key="bud_sk_test123")
        assert auth.is_authenticated is True

    def test_api_key_auth_is_authenticated_empty_key(self) -> None:
        """is_authenticated should return False when key is empty."""
        auth = APIKeyAuth(api_key="")
        assert auth.is_authenticated is False

    def test_api_key_auth_refresh_does_nothing(self) -> None:
        """refresh should not modify the API key."""
        auth = APIKeyAuth(api_key="bud_sk_test123")
        client = httpx.Client(base_url="https://api.example.com")

        original_key = auth.api_key
        auth.refresh(client)

        assert auth.api_key == original_key

    def test_api_key_auth_different_key_formats(self) -> None:
        """API key auth should work with various key formats."""
        # Standard format
        auth1 = APIKeyAuth(api_key="bud_sk_abc123")
        assert auth1.get_headers() == {"Authorization": "Bearer bud_sk_abc123"}

        # Long key
        long_key = "bud_sk_" + "a" * 100
        auth2 = APIKeyAuth(api_key=long_key)
        assert auth2.get_headers() == {"Authorization": f"Bearer {long_key}"}

        # Simple key
        auth3 = APIKeyAuth(api_key="simple-key")
        assert auth3.get_headers() == {"Authorization": "Bearer simple-key"}
