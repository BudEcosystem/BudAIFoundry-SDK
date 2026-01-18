"""Tests for JWT authentication provider."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import httpx
import pytest
import respx

from bud.auth import AuthProvider, JWTAuth


class TestJWTAuth:
    """Test JWTAuth authentication provider."""

    def test_jwt_auth_inherits_auth_provider(self) -> None:
        """JWTAuth should inherit from AuthProvider."""
        auth = JWTAuth(email="test@example.com", password="secret")
        assert isinstance(auth, AuthProvider)

    def test_jwt_auth_initial_state_not_authenticated(self) -> None:
        """JWTAuth should not be authenticated before login."""
        auth = JWTAuth(email="test@example.com", password="secret")
        assert auth.is_authenticated is False

    def test_jwt_auth_get_headers_empty_when_not_authenticated(self) -> None:
        """get_headers should return empty dict when not authenticated."""
        auth = JWTAuth(email="test@example.com", password="secret")
        assert auth.get_headers() == {}

    def test_jwt_auth_needs_refresh_when_not_authenticated(self) -> None:
        """needs_refresh should return True when not authenticated."""
        auth = JWTAuth(email="test@example.com", password="secret")
        assert auth.needs_refresh() is True

    @respx.mock
    def test_jwt_auth_login_success(self) -> None:
        """login should successfully authenticate with valid credentials."""
        respx.post("https://api.example.com/auth/login").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "test-access-token",
                    "refresh_token": "test-refresh-token",
                    "expires_in": 3600,
                },
            )
        )

        auth = JWTAuth(email="test@example.com", password="secret")
        client = httpx.Client(base_url="https://api.example.com")

        result = auth.login(client)

        assert result["access_token"] == "test-access-token"
        assert auth.is_authenticated is True

    @respx.mock
    def test_jwt_auth_login_invalid_credentials(self) -> None:
        """login should raise error with invalid credentials."""
        respx.post("https://api.example.com/auth/login").mock(
            return_value=httpx.Response(
                401,
                json={"error": "Invalid credentials"},
            )
        )

        auth = JWTAuth(email="test@example.com", password="wrong")
        client = httpx.Client(base_url="https://api.example.com")

        with pytest.raises(httpx.HTTPStatusError):
            auth.login(client)

    @respx.mock
    def test_jwt_auth_login_sets_tokens(self) -> None:
        """login should set access and refresh tokens."""
        respx.post("https://api.example.com/auth/login").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "my-access-token",
                    "refresh_token": "my-refresh-token",
                    "expires_in": 3600,
                },
            )
        )

        auth = JWTAuth(email="test@example.com", password="secret")
        client = httpx.Client(base_url="https://api.example.com")
        auth.login(client)

        assert auth._access_token == "my-access-token"
        assert auth._refresh_token == "my-refresh-token"

    @respx.mock
    def test_jwt_auth_login_sets_expiry(self) -> None:
        """login should set expiry time based on expires_in."""
        respx.post("https://api.example.com/auth/login").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "test-token",
                    "refresh_token": "test-refresh",
                    "expires_in": 3600,
                },
            )
        )

        auth = JWTAuth(email="test@example.com", password="secret")
        client = httpx.Client(base_url="https://api.example.com")

        before = time.time()
        auth.login(client)
        after = time.time()

        # Expiry should be approximately now + 3600
        assert auth._expires_at >= before + 3600
        assert auth._expires_at <= after + 3600

    @respx.mock
    def test_jwt_auth_get_headers_returns_bearer_token(self) -> None:
        """get_headers should return Bearer token after login."""
        respx.post("https://api.example.com/auth/login").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "my-jwt-token",
                    "refresh_token": "refresh",
                    "expires_in": 3600,
                },
            )
        )

        auth = JWTAuth(email="test@example.com", password="secret")
        client = httpx.Client(base_url="https://api.example.com")
        auth.login(client)

        headers = auth.get_headers()
        assert headers == {"Authorization": "Bearer my-jwt-token"}

    @respx.mock
    def test_jwt_auth_needs_refresh_before_expiry(self) -> None:
        """needs_refresh should return True when close to expiry."""
        respx.post("https://api.example.com/auth/login").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "test-token",
                    "refresh_token": "refresh",
                    "expires_in": 30,  # Expires in 30 seconds
                },
            )
        )

        auth = JWTAuth(email="test@example.com", password="secret")
        auth._refresh_buffer = 60  # Refresh 60 seconds before expiry
        client = httpx.Client(base_url="https://api.example.com")
        auth.login(client)

        # Should need refresh since 30s < 60s buffer
        assert auth.needs_refresh() is True

    @respx.mock
    def test_jwt_auth_no_refresh_needed_when_fresh(self) -> None:
        """needs_refresh should return False when token is fresh."""
        respx.post("https://api.example.com/auth/login").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "test-token",
                    "refresh_token": "refresh",
                    "expires_in": 3600,  # Expires in 1 hour
                },
            )
        )

        auth = JWTAuth(email="test@example.com", password="secret")
        auth._refresh_buffer = 60  # Refresh 60 seconds before expiry
        client = httpx.Client(base_url="https://api.example.com")
        auth.login(client)

        # Should not need refresh since 3600s > 60s buffer
        assert auth.needs_refresh() is False

    @respx.mock
    def test_jwt_auth_refresh_token_success(self) -> None:
        """refresh should update tokens using refresh_token."""
        # Initial login
        respx.post("https://api.example.com/auth/login").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "old-token",
                    "refresh_token": "old-refresh",
                    "expires_in": 3600,
                },
            )
        )

        # Token refresh
        respx.post("https://api.example.com/auth/refresh-token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "new-token",
                    "refresh_token": "new-refresh",
                    "expires_in": 3600,
                },
            )
        )

        auth = JWTAuth(email="test@example.com", password="secret")
        client = httpx.Client(base_url="https://api.example.com")
        auth.login(client)

        assert auth._access_token == "old-token"

        auth.refresh(client)

        assert auth._access_token == "new-token"
        assert auth._refresh_token == "new-refresh"

    @respx.mock
    def test_jwt_auth_refresh_relogins_on_failure(self) -> None:
        """refresh should re-login if refresh token fails."""
        login_route = respx.post("https://api.example.com/auth/login").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "fresh-token",
                    "refresh_token": "fresh-refresh",
                    "expires_in": 3600,
                },
            )
        )

        # Refresh fails with 401
        respx.post("https://api.example.com/auth/refresh-token").mock(
            return_value=httpx.Response(401, json={"error": "Token expired"})
        )

        auth = JWTAuth(email="test@example.com", password="secret")
        client = httpx.Client(base_url="https://api.example.com")
        auth.login(client)

        # First call to login
        assert login_route.call_count == 1

        auth.refresh(client)

        # Should have re-logged in
        assert login_route.call_count == 2
        assert auth._access_token == "fresh-token"

    @respx.mock
    def test_jwt_auth_logout_clears_tokens(self) -> None:
        """logout should clear all tokens."""
        respx.post("https://api.example.com/auth/login").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "test-token",
                    "refresh_token": "refresh",
                    "expires_in": 3600,
                },
            )
        )
        respx.post("https://api.example.com/auth/logout").mock(
            return_value=httpx.Response(200, json={"success": True})
        )

        auth = JWTAuth(email="test@example.com", password="secret")
        client = httpx.Client(base_url="https://api.example.com")
        auth.login(client)

        assert auth.is_authenticated is True

        auth.logout(client)

        assert auth.is_authenticated is False
        assert auth._access_token is None
        assert auth._refresh_token is None
        assert auth._expires_at == 0.0

    @respx.mock
    def test_jwt_auth_is_authenticated_checks_expiry(self) -> None:
        """is_authenticated should return False if token is expired."""
        respx.post("https://api.example.com/auth/login").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "test-token",
                    "refresh_token": "refresh",
                    "expires_in": 3600,
                },
            )
        )

        auth = JWTAuth(email="test@example.com", password="secret")
        client = httpx.Client(base_url="https://api.example.com")
        auth.login(client)

        assert auth.is_authenticated is True

        # Manually expire the token
        auth._expires_at = time.time() - 100

        assert auth.is_authenticated is False
