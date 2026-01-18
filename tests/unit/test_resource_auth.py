"""Tests for Auth resource."""

from __future__ import annotations

import time

import httpx
import pytest
import respx

from bud._http import HttpClient
from bud.auth import JWTAuth
from bud.resources.auth import Auth


class TestAuthResource:
    """Test Auth resource methods."""

    @respx.mock
    def test_auth_resource_login(self) -> None:
        """Auth resource should login and return token info."""
        respx.post("https://api.example.com/auth/login").mock(
            return_value=httpx.Response(
                200,
                json={
                    "object": "auth_token",
                    "message": "User logged in successfully",
                    "token": {
                        "access_token": "new-access-token",
                        "refresh_token": "new-refresh-token",
                        "expires_in": 3600,
                        "token_type": "Bearer",
                    },
                    "first_login": False,
                    "is_reset_password": False,
                },
            )
        )

        http = HttpClient(base_url="https://api.example.com")
        auth_resource = Auth(http)

        result = auth_resource.login(email="user@example.com", password="secret")

        assert result.access_token == "new-access-token"
        assert result.refresh_token == "new-refresh-token"
        assert result.expires_in == 3600
        assert result.token.token_type == "Bearer"

    @respx.mock
    def test_auth_resource_login_invalid_credentials(self) -> None:
        """Auth resource should raise error on invalid credentials."""
        respx.post("https://api.example.com/auth/login").mock(
            return_value=httpx.Response(
                401,
                json={"message": "Invalid email or password"},
            )
        )

        http = HttpClient(base_url="https://api.example.com")
        auth_resource = Auth(http)

        from bud.exceptions import AuthenticationError

        with pytest.raises(AuthenticationError):
            auth_resource.login(email="bad@example.com", password="wrong")

    @respx.mock
    def test_auth_resource_logout(self) -> None:
        """Auth resource should logout successfully."""
        respx.post("https://api.example.com/auth/logout").mock(
            return_value=httpx.Response(204)
        )

        # Use authenticated client
        auth = JWTAuth(email="test@example.com", password="secret")
        auth._access_token = "current-token"
        auth._refresh_token = "current-refresh"
        auth._expires_at = time.time() + 3600

        http = HttpClient(base_url="https://api.example.com", auth=auth)
        auth_resource = Auth(http)

        # Should not raise
        auth_resource.logout()

    @respx.mock
    def test_auth_resource_refresh(self) -> None:
        """Auth resource should refresh tokens."""
        respx.post("https://api.example.com/auth/refresh-token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "object": "auth_token",
                    "message": "Token refreshed",
                    "token": {
                        "access_token": "refreshed-access-token",
                        "refresh_token": "refreshed-refresh-token",
                        "expires_in": 3600,
                        "token_type": "Bearer",
                    },
                    "first_login": False,
                    "is_reset_password": False,
                },
            )
        )

        http = HttpClient(base_url="https://api.example.com")
        auth_resource = Auth(http)

        result = auth_resource.refresh(refresh_token="old-refresh-token")

        assert result.access_token == "refreshed-access-token"
        assert result.refresh_token == "refreshed-refresh-token"

    @respx.mock
    def test_auth_resource_status_authenticated(self) -> None:
        """Auth resource should return status when authenticated."""
        respx.get("https://api.example.com/auth/me").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "user-123",
                    "email": "user@example.com",
                    "name": "Test User",
                    "is_active": True,
                },
            )
        )

        auth = JWTAuth(email="test@example.com", password="secret")
        auth._access_token = "valid-token"
        auth._refresh_token = "refresh-token"
        auth._expires_at = time.time() + 3600

        http = HttpClient(base_url="https://api.example.com", auth=auth)
        auth_resource = Auth(http)

        result = auth_resource.status()

        assert result.id == "user-123"
        assert result.email == "user@example.com"
        assert result.name == "Test User"
        assert result.is_active is True

    @respx.mock
    def test_auth_resource_status_unauthenticated(self) -> None:
        """Auth resource should raise error when not authenticated."""
        respx.get("https://api.example.com/auth/me").mock(
            return_value=httpx.Response(
                401,
                json={"message": "Not authenticated"},
            )
        )

        http = HttpClient(base_url="https://api.example.com")
        auth_resource = Auth(http)

        from bud.exceptions import AuthenticationError

        with pytest.raises(AuthenticationError):
            auth_resource.status()

    @respx.mock
    def test_auth_resource_register(self) -> None:
        """Auth resource should register a new user."""
        respx.post("https://api.example.com/auth/register").mock(
            return_value=httpx.Response(
                201,
                json={
                    "id": "new-user-123",
                    "email": "newuser@example.com",
                    "name": "New User",
                    "is_active": True,
                },
            )
        )

        http = HttpClient(base_url="https://api.example.com")
        auth_resource = Auth(http)

        result = auth_resource.register(
            email="newuser@example.com",
            password="secure-password",
            name="New User",
        )

        assert result.id == "new-user-123"
        assert result.email == "newuser@example.com"
        assert result.name == "New User"

    @respx.mock
    def test_auth_resource_register_duplicate_email(self) -> None:
        """Auth resource should raise error on duplicate email."""
        respx.post("https://api.example.com/auth/register").mock(
            return_value=httpx.Response(
                422,
                json={
                    "message": "Email already registered",
                    "errors": [{"field": "email", "message": "Email already exists"}],
                },
            )
        )

        http = HttpClient(base_url="https://api.example.com")
        auth_resource = Auth(http)

        from bud.exceptions import ValidationError

        with pytest.raises(ValidationError):
            auth_resource.register(
                email="existing@example.com",
                password="password",
                name="Existing User",
            )
