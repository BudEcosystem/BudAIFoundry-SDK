"""Tests for HTTP client auto token refresh."""

from __future__ import annotations

import time

import httpx
import pytest
import respx

from bud._http import HttpClient
from bud.auth import JWTAuth
from bud.exceptions import AuthenticationError


class TestHttpClientAutoRefresh:
    """Test HTTP client auto token refresh behavior."""

    @respx.mock
    def test_http_client_refreshes_before_request_if_needed(self) -> None:
        """HttpClient should refresh token before request if needed."""
        # Setup login mock
        respx.post("https://api.example.com/auth/login").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "new-token",
                    "refresh_token": "refresh",
                    "expires_in": 3600,
                },
            )
        )

        # Setup data endpoint mock
        data_route = respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(200, json={"result": "success"})
        )

        # Create auth that needs refresh
        auth = JWTAuth(email="test@example.com", password="secret")
        # auth.needs_refresh() will return True since not authenticated

        client = HttpClient(
            base_url="https://api.example.com",
            auth=auth,
        )

        result = client.get("/data")

        assert result == {"result": "success"}
        # Should have called the data endpoint with the new token
        request = data_route.calls.last.request
        assert request.headers.get("Authorization") == "Bearer new-token"

    @respx.mock
    def test_http_client_retries_on_401(self) -> None:
        """HttpClient should retry request after 401 and token refresh."""
        # First call returns 401
        # Second call (after refresh) returns success
        call_count = {"value": 0}

        def data_response(_request: httpx.Request) -> httpx.Response:
            call_count["value"] += 1
            if call_count["value"] == 1:
                return httpx.Response(401, json={"error": "Unauthorized"})
            return httpx.Response(200, json={"result": "success"})

        respx.get("https://api.example.com/data").mock(side_effect=data_response)

        # Setup refresh mock
        respx.post("https://api.example.com/auth/refresh-token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "refreshed-token",
                    "refresh_token": "new-refresh",
                    "expires_in": 3600,
                },
            )
        )

        # Create authenticated auth
        auth = JWTAuth(email="test@example.com", password="secret")
        auth._access_token = "old-token"
        auth._refresh_token = "old-refresh"
        auth._expires_at = time.time() + 3600  # Not expired

        client = HttpClient(
            base_url="https://api.example.com",
            auth=auth,
        )

        result = client.get("/data")

        assert result == {"result": "success"}
        assert call_count["value"] == 2  # Called twice

    @respx.mock
    def test_http_client_refresh_and_retry_on_401(self) -> None:
        """HttpClient should refresh token and retry on 401."""
        call_count = {"value": 0}

        def data_response(_request: httpx.Request) -> httpx.Response:
            call_count["value"] += 1
            if call_count["value"] == 1:
                return httpx.Response(401, json={"error": "Token expired"})
            return httpx.Response(200, json={"data": "ok"})

        respx.get("https://api.example.com/resource").mock(side_effect=data_response)

        respx.post("https://api.example.com/auth/refresh-token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "new-access-token",
                    "refresh_token": "new-refresh-token",
                    "expires_in": 3600,
                },
            )
        )

        auth = JWTAuth(email="test@example.com", password="secret")
        auth._access_token = "expired-token"
        auth._refresh_token = "valid-refresh"
        auth._expires_at = time.time() + 3600

        client = HttpClient(
            base_url="https://api.example.com",
            auth=auth,
        )

        result = client.get("/resource")

        assert result == {"data": "ok"}
        assert auth._access_token == "new-access-token"

    @respx.mock
    def test_http_client_raises_after_refresh_fails(self) -> None:
        """HttpClient should raise AuthenticationError if refresh fails."""
        # Data endpoint always returns 401
        respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )

        # Refresh also fails
        respx.post("https://api.example.com/auth/refresh-token").mock(
            return_value=httpx.Response(401, json={"error": "Invalid refresh token"})
        )

        # Re-login also fails
        respx.post("https://api.example.com/auth/login").mock(
            return_value=httpx.Response(401, json={"error": "Invalid credentials"})
        )

        auth = JWTAuth(email="test@example.com", password="secret")
        auth._access_token = "old-token"
        auth._refresh_token = "old-refresh"
        auth._expires_at = time.time() + 3600

        client = HttpClient(
            base_url="https://api.example.com",
            auth=auth,
        )

        with pytest.raises(AuthenticationError):
            client.get("/data")

    @respx.mock
    def test_http_client_no_retry_on_other_4xx(self) -> None:
        """HttpClient should not retry on non-401 4xx errors."""
        respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(403, json={"error": "Forbidden"})
        )

        auth = JWTAuth(email="test@example.com", password="secret")
        auth._access_token = "valid-token"
        auth._refresh_token = "refresh"
        auth._expires_at = time.time() + 3600

        client = HttpClient(
            base_url="https://api.example.com",
            auth=auth,
        )

        # Should raise immediately without retry
        from bud.exceptions import BudError

        with pytest.raises(BudError):
            client.get("/data")
