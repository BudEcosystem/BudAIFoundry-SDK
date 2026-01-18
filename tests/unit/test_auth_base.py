"""Tests for AuthProvider base interface."""

from __future__ import annotations

import pytest

from bud.auth import AuthProvider


class TestAuthProviderInterface:
    """Test AuthProvider is an abstract base class with required methods."""

    def test_auth_provider_is_abstract(self) -> None:
        """AuthProvider cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            AuthProvider()  # type: ignore

    def test_auth_provider_requires_get_headers(self) -> None:
        """AuthProvider requires get_headers method."""

        class IncompleteAuth(AuthProvider):
            def needs_refresh(self) -> bool:
                return False

            def refresh(self, client) -> None:
                pass

            @property
            def is_authenticated(self) -> bool:
                return True

        with pytest.raises(TypeError, match="get_headers"):
            IncompleteAuth()  # type: ignore

    def test_auth_provider_requires_needs_refresh(self) -> None:
        """AuthProvider requires needs_refresh method."""

        class IncompleteAuth(AuthProvider):
            def get_headers(self) -> dict[str, str]:
                return {}

            def refresh(self, client) -> None:
                pass

            @property
            def is_authenticated(self) -> bool:
                return True

        with pytest.raises(TypeError, match="needs_refresh"):
            IncompleteAuth()  # type: ignore

    def test_auth_provider_requires_is_authenticated(self) -> None:
        """AuthProvider requires is_authenticated property."""

        class IncompleteAuth(AuthProvider):
            def get_headers(self) -> dict[str, str]:
                return {}

            def needs_refresh(self) -> bool:
                return False

            def refresh(self, client) -> None:
                pass

        with pytest.raises(TypeError, match="is_authenticated"):
            IncompleteAuth()  # type: ignore

    def test_auth_provider_complete_implementation(self) -> None:
        """A complete implementation can be instantiated."""

        class CompleteAuth(AuthProvider):
            def get_headers(self) -> dict[str, str]:
                return {"X-Custom": "header"}

            def needs_refresh(self) -> bool:
                return False

            def refresh(self, client) -> None:
                pass

            @property
            def is_authenticated(self) -> bool:
                return True

        auth = CompleteAuth()
        assert auth.get_headers() == {"X-Custom": "header"}
        assert auth.needs_refresh() is False
        assert auth.is_authenticated is True
