"""Tests for Dapr authentication provider."""

from __future__ import annotations

import httpx

from bud.auth import AuthProvider, DaprAuth


class TestDaprAuth:
    """Test DaprAuth authentication provider."""

    def test_dapr_auth_inherits_auth_provider(self) -> None:
        """DaprAuth should inherit from AuthProvider."""
        auth = DaprAuth(token="test-token")
        assert isinstance(auth, AuthProvider)

    def test_dapr_auth_get_headers_with_token(self) -> None:
        """get_headers should return dapr-api-token header."""
        auth = DaprAuth(token="my-dapr-token")
        headers = auth.get_headers()

        assert headers == {"dapr-api-token": "my-dapr-token"}

    def test_dapr_auth_get_headers_with_user_id(self) -> None:
        """get_headers should include X-User-ID when provided."""
        auth = DaprAuth(token="my-dapr-token", user_id="user-123")
        headers = auth.get_headers()

        assert headers == {
            "dapr-api-token": "my-dapr-token",
            "X-User-ID": "user-123",
        }

    def test_dapr_auth_get_headers_without_user_id(self) -> None:
        """get_headers should not include X-User-ID when not provided."""
        auth = DaprAuth(token="my-dapr-token", user_id=None)
        headers = auth.get_headers()

        assert "X-User-ID" not in headers
        assert headers == {"dapr-api-token": "my-dapr-token"}

    def test_dapr_auth_needs_refresh_always_false(self) -> None:
        """needs_refresh should always return False for Dapr tokens."""
        auth = DaprAuth(token="my-dapr-token")
        assert auth.needs_refresh() is False

    def test_dapr_auth_is_authenticated_with_token(self) -> None:
        """is_authenticated should return True when token is present."""
        auth = DaprAuth(token="my-dapr-token")
        assert auth.is_authenticated is True

    def test_dapr_auth_is_authenticated_without_token(self) -> None:
        """is_authenticated should return False when token is empty."""
        auth = DaprAuth(token="")
        assert auth.is_authenticated is False

    def test_dapr_auth_refresh_does_nothing(self) -> None:
        """refresh should not modify the token."""
        auth = DaprAuth(token="my-dapr-token", user_id="user-123")
        client = httpx.Client(base_url="https://api.example.com")

        # Store original values
        original_token = auth.token
        original_user_id = auth.user_id

        auth.refresh(client)

        # Values should be unchanged
        assert auth.token == original_token
        assert auth.user_id == original_user_id

    def test_dapr_auth_token_is_required(self) -> None:
        """DaprAuth should require a token parameter."""
        # This should work (token provided)
        auth = DaprAuth(token="test")
        assert auth.token == "test"

        # Empty token is technically allowed but not authenticated
        auth_empty = DaprAuth(token="")
        assert auth_empty.is_authenticated is False
