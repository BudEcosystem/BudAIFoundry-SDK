"""Integration tests for JWT authentication flow.

These tests require a live API server.
Run with: pytest tests/integration/ -v --integration
"""

from __future__ import annotations

import os
import time

import pytest

# Skip all tests if not running integration tests
pytestmark = pytest.mark.integration


@pytest.fixture
def jwt_credentials():
    """Get JWT credentials from environment.

    Set these environment variables:
    - BUD_TEST_EMAIL: Test user email
    - BUD_TEST_PASSWORD: Test user password
    - BUD_TEST_BASE_URL: API base URL
    """
    email = os.getenv("BUD_TEST_EMAIL")
    password = os.getenv("BUD_TEST_PASSWORD")
    base_url = os.getenv("BUD_TEST_BASE_URL")

    if not all([email, password, base_url]):
        pytest.skip("Integration test credentials not configured")

    return {
        "email": email,
        "password": password,
        "base_url": base_url,
    }


class TestJWTAuthFlow:
    """Test full JWT authentication flow against live API."""

    def test_full_jwt_login_flow(self, jwt_credentials: dict) -> None:
        """Test complete login flow with email/password."""
        from bud.client import BudClient

        client = BudClient(
            email=jwt_credentials["email"],
            password=jwt_credentials["password"],
            base_url=jwt_credentials["base_url"],
        )

        # Client should have JWTAuth
        from bud.auth import JWTAuth

        assert isinstance(client._auth, JWTAuth)

        # Should be able to make authenticated requests
        # The auth will auto-login on first request
        try:
            pipelines = client.pipelines.list()
            assert hasattr(pipelines, "items") or isinstance(pipelines, list)
        finally:
            client.close()

    def test_jwt_token_refresh(self, jwt_credentials: dict) -> None:
        """Test token refresh functionality."""
        from bud.auth import JWTAuth

        auth = JWTAuth(
            email=jwt_credentials["email"],
            password=jwt_credentials["password"],
        )

        # Login first
        import httpx

        with httpx.Client() as client:
            auth.login(client, jwt_credentials["base_url"])

            # Should now be authenticated
            assert auth.is_authenticated
            assert auth._access_token is not None
            assert auth._refresh_token is not None

            # Force refresh
            auth.refresh(client, jwt_credentials["base_url"])

            # Token should be different after refresh
            # (or the same if server returns same token)
            assert auth.is_authenticated

    def test_jwt_auth_resource_login(self, jwt_credentials: dict) -> None:
        """Test login via auth resource."""
        from bud._http import HttpClient
        from bud.resources.auth import Auth

        http = HttpClient(base_url=jwt_credentials["base_url"])

        try:
            auth_resource = Auth(http)
            result = auth_resource.login(
                email=jwt_credentials["email"],
                password=jwt_credentials["password"],
            )

            assert result.access_token is not None
            assert result.refresh_token is not None
            assert result.expires_in > 0
        finally:
            http.close()


class TestJWTTokenExpiry:
    """Test JWT token expiry handling."""

    def test_jwt_auth_checks_expiry(self, jwt_credentials: dict) -> None:
        """Test that auth checks token expiry."""
        from bud.auth import JWTAuth

        auth = JWTAuth(
            email=jwt_credentials["email"],
            password=jwt_credentials["password"],
        )

        # Not authenticated initially
        assert not auth.is_authenticated

        # Should need refresh
        assert auth.needs_refresh()

        # After login
        import httpx

        with httpx.Client() as client:
            auth.login(client, jwt_credentials["base_url"])

            # Now authenticated
            assert auth.is_authenticated

            # Should not need refresh if token is fresh
            if auth._expires_at > time.time() + 60:
                assert not auth.needs_refresh()
