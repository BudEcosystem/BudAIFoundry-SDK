"""Tests for BudClient auth resolution."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from bud.auth import APIKeyAuth, AuthProvider, DaprAuth, JWTAuth
from bud.client import BudClient


class TestBudClientAuthResolution:
    """Test BudClient auth provider resolution."""

    def test_client_with_email_password_uses_jwt(self) -> None:
        """Client with email/password should use JWTAuth."""
        client = BudClient(
            email="test@example.com",
            password="secret",
            base_url="https://api.example.com",
        )

        assert isinstance(client._auth, JWTAuth)
        assert client._auth.email == "test@example.com"
        assert client._auth.password == "secret"

    def test_client_with_dapr_token_uses_dapr(self) -> None:
        """Client with dapr_token should use DaprAuth."""
        client = BudClient(
            dapr_token="my-dapr-token",
            base_url="https://api.example.com",
        )

        assert isinstance(client._auth, DaprAuth)
        assert client._auth.token == "my-dapr-token"

    def test_client_with_dapr_token_and_user_id(self) -> None:
        """Client with dapr_token and user_id should pass both to DaprAuth."""
        client = BudClient(
            dapr_token="my-dapr-token",
            user_id="user-123",
            base_url="https://api.example.com",
        )

        assert isinstance(client._auth, DaprAuth)
        assert client._auth.token == "my-dapr-token"
        assert client._auth.user_id == "user-123"

    def test_client_with_api_key_uses_apikey(self) -> None:
        """Client with api_key should use APIKeyAuth."""
        client = BudClient(
            api_key="bud_sk_test123",
            base_url="https://api.example.com",
        )

        assert isinstance(client._auth, APIKeyAuth)
        assert client._auth.api_key == "bud_sk_test123"

    def test_client_with_auth_provider_uses_directly(self) -> None:
        """Client with explicit auth provider should use it directly."""

        class CustomAuth(AuthProvider):
            def get_headers(self) -> dict[str, str]:
                return {"X-Custom": "auth"}

            def needs_refresh(self) -> bool:
                return False

            def refresh(self, client) -> None:
                pass

            @property
            def is_authenticated(self) -> bool:
                return True

        custom_auth = CustomAuth()
        client = BudClient(
            auth=custom_auth,
            base_url="https://api.example.com",
        )

        assert client._auth is custom_auth

    def test_client_prefers_explicit_over_env(self) -> None:
        """Explicit params should take precedence over env vars."""
        with patch.dict(
            os.environ,
            {
                "BUD_API_KEY": "env-api-key",
                "BUD_DAPR_TOKEN": "env-dapr-token",
            },
        ):
            client = BudClient(
                api_key="explicit-api-key",
                base_url="https://api.example.com",
            )

            assert isinstance(client._auth, APIKeyAuth)
            assert client._auth.api_key == "explicit-api-key"

    def test_client_raises_without_any_auth(self) -> None:
        """Client should raise ValueError without any auth credentials."""
        # Clear any env vars that might provide auth
        with patch.dict(
            os.environ,
            {
                "BUD_API_KEY": "",
                "BUD_DAPR_TOKEN": "",
                "BUD_EMAIL": "",
                "BUD_PASSWORD": "",
            },
            clear=True,
        ):
            with pytest.raises(ValueError, match="No authentication"):
                BudClient(base_url="https://api.example.com")

    def test_client_auth_priority_api_key_first(self) -> None:
        """API key should have highest priority when multiple provided."""
        client = BudClient(
            api_key="my-api-key",
            dapr_token="my-dapr-token",
            email="test@example.com",
            password="secret",
            base_url="https://api.example.com",
        )

        assert isinstance(client._auth, APIKeyAuth)

    def test_client_auth_priority_dapr_over_jwt(self) -> None:
        """Dapr token should have priority over JWT credentials."""
        client = BudClient(
            dapr_token="my-dapr-token",
            email="test@example.com",
            password="secret",
            base_url="https://api.example.com",
        )

        assert isinstance(client._auth, DaprAuth)


class TestBudClientEnvAuth:
    """Test BudClient auth from environment variables."""

    def test_client_from_env_bud_api_key(self) -> None:
        """Client should use BUD_API_KEY from environment."""
        with patch.dict(os.environ, {"BUD_API_KEY": "env-api-key"}, clear=True):
            client = BudClient(base_url="https://api.example.com")

            assert isinstance(client._auth, APIKeyAuth)
            assert client._auth.api_key == "env-api-key"

    def test_client_from_env_bud_dapr_token(self) -> None:
        """Client should use BUD_DAPR_TOKEN from environment."""
        with patch.dict(os.environ, {"BUD_DAPR_TOKEN": "env-dapr-token"}, clear=True):
            client = BudClient(base_url="https://api.example.com")

            assert isinstance(client._auth, DaprAuth)
            assert client._auth.token == "env-dapr-token"

    def test_client_from_env_bud_dapr_token_with_user_id(self) -> None:
        """Client should use BUD_USER_ID with BUD_DAPR_TOKEN."""
        with patch.dict(
            os.environ,
            {"BUD_DAPR_TOKEN": "env-dapr-token", "BUD_USER_ID": "env-user-id"},
            clear=True,
        ):
            client = BudClient(base_url="https://api.example.com")

            assert isinstance(client._auth, DaprAuth)
            assert client._auth.token == "env-dapr-token"
            assert client._auth.user_id == "env-user-id"

    def test_client_from_env_bud_email_password(self) -> None:
        """Client should use BUD_EMAIL and BUD_PASSWORD from environment."""
        with patch.dict(
            os.environ,
            {"BUD_EMAIL": "env@example.com", "BUD_PASSWORD": "env-secret"},
            clear=True,
        ):
            client = BudClient(base_url="https://api.example.com")

            assert isinstance(client._auth, JWTAuth)
            assert client._auth.email == "env@example.com"
            assert client._auth.password == "env-secret"

    def test_client_env_priority_api_key_first(self) -> None:
        """BUD_API_KEY should have highest priority among env vars."""
        with patch.dict(
            os.environ,
            {
                "BUD_API_KEY": "env-api-key",
                "BUD_DAPR_TOKEN": "env-dapr-token",
                "BUD_EMAIL": "env@example.com",
                "BUD_PASSWORD": "env-secret",
            },
            clear=True,
        ):
            client = BudClient(base_url="https://api.example.com")

            assert isinstance(client._auth, APIKeyAuth)

    def test_client_env_priority_dapr_second(self) -> None:
        """BUD_DAPR_TOKEN should have second priority among env vars."""
        with patch.dict(
            os.environ,
            {
                "BUD_DAPR_TOKEN": "env-dapr-token",
                "BUD_EMAIL": "env@example.com",
                "BUD_PASSWORD": "env-secret",
            },
            clear=True,
        ):
            client = BudClient(base_url="https://api.example.com")

            assert isinstance(client._auth, DaprAuth)

    def test_client_env_priority_jwt_third(self) -> None:
        """BUD_EMAIL/BUD_PASSWORD should have lowest priority among env vars."""
        with patch.dict(
            os.environ,
            {"BUD_EMAIL": "env@example.com", "BUD_PASSWORD": "env-secret"},
            clear=True,
        ):
            client = BudClient(base_url="https://api.example.com")

            assert isinstance(client._auth, JWTAuth)

    def test_client_base_url_from_env(self) -> None:
        """Client should use BUD_BASE_URL from environment."""
        with patch.dict(
            os.environ,
            {"BUD_API_KEY": "test-key", "BUD_BASE_URL": "https://custom.api.com"},
            clear=True,
        ):
            client = BudClient()

            assert client._base_url == "https://custom.api.com"
