"""Tests for HTTP client auth integration."""

from __future__ import annotations

import httpx
import pytest
import respx

from bud._http import HttpClient
from bud.auth import APIKeyAuth, DaprAuth, JWTAuth


class TestHttpClientAuthIntegration:
    """Test HTTP client auth provider integration."""

    def test_http_client_accepts_auth_provider(self) -> None:
        """HttpClient should accept an auth provider parameter."""
        auth = APIKeyAuth(api_key="test-key")
        client = HttpClient(
            base_url="https://api.example.com",
            auth=auth,
        )
        assert client._auth is auth

    def test_http_client_works_without_auth_provider(self) -> None:
        """HttpClient should work without an auth provider."""
        client = HttpClient(base_url="https://api.example.com")
        assert client._auth is None

    @respx.mock
    def test_http_client_injects_auth_headers(self) -> None:
        """HttpClient should inject auth headers into requests."""
        route = respx.get("https://api.example.com/test").mock(
            return_value=httpx.Response(200, json={"data": "test"})
        )

        auth = APIKeyAuth(api_key="bud_sk_test123")
        client = HttpClient(
            base_url="https://api.example.com",
            auth=auth,
        )

        result = client.get("/test")

        assert result == {"data": "test"}
        assert route.called
        request = route.calls.last.request
        assert request.headers.get("Authorization") == "Bearer bud_sk_test123"

    @respx.mock
    def test_http_client_injects_dapr_headers(self) -> None:
        """HttpClient should inject Dapr auth headers."""
        route = respx.get("https://api.example.com/test").mock(
            return_value=httpx.Response(200, json={"data": "test"})
        )

        auth = DaprAuth(token="dapr-token", user_id="user-123")
        client = HttpClient(
            base_url="https://api.example.com",
            auth=auth,
        )

        result = client.get("/test")

        assert result == {"data": "test"}
        request = route.calls.last.request
        assert request.headers.get("dapr-api-token") == "dapr-token"
        assert request.headers.get("X-User-ID") == "user-123"

    @respx.mock
    def test_http_client_no_auth_headers_without_provider(self) -> None:
        """HttpClient should not add auth headers without provider."""
        route = respx.get("https://api.example.com/test").mock(
            return_value=httpx.Response(200, json={"data": "test"})
        )

        client = HttpClient(base_url="https://api.example.com")
        result = client.get("/test")

        assert result == {"data": "test"}
        request = route.calls.last.request
        assert "Authorization" not in request.headers
        assert "dapr-api-token" not in request.headers

    @respx.mock
    def test_http_client_post_with_auth(self) -> None:
        """HttpClient POST should include auth headers."""
        route = respx.post("https://api.example.com/data").mock(
            return_value=httpx.Response(201, json={"id": "123"})
        )

        auth = APIKeyAuth(api_key="test-key")
        client = HttpClient(
            base_url="https://api.example.com",
            auth=auth,
        )

        result = client.post("/data", json={"name": "test"})

        assert result == {"id": "123"}
        request = route.calls.last.request
        assert request.headers.get("Authorization") == "Bearer test-key"

    @respx.mock
    def test_http_client_preserves_default_headers(self) -> None:
        """HttpClient should preserve default headers along with auth."""
        route = respx.get("https://api.example.com/test").mock(
            return_value=httpx.Response(200, json={"data": "test"})
        )

        auth = APIKeyAuth(api_key="test-key")
        client = HttpClient(
            base_url="https://api.example.com",
            auth=auth,
        )

        client.get("/test")

        request = route.calls.last.request
        # Should have auth header
        assert request.headers.get("Authorization") == "Bearer test-key"
        # Should have default headers
        assert "User-Agent" in request.headers
        assert "application/json" in request.headers.get("Accept", "")
