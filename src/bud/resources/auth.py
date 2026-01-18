"""Auth resource for BudAI SDK."""

from __future__ import annotations

from typing import TYPE_CHECKING

from bud.models.auth import TokenResponse, UserInfo
from bud.resources._base import SyncResource

if TYPE_CHECKING:
    from bud._http import HttpClient


class Auth(SyncResource):
    """Authentication resource for JWT auth management.

    This resource provides methods for managing JWT authentication,
    including login, logout, token refresh, and checking auth status.

    Example:
        ```python
        from bud import BudClient

        # Create client (may not be authenticated yet)
        client = BudClient(base_url="https://api.example.com")

        # Login to get tokens
        tokens = client.auth.login(email="user@example.com", password="secret")
        print(f"Logged in, token expires in {tokens.expires_in}s")

        # Check current user
        user = client.auth.status()
        print(f"Logged in as: {user.email}")

        # Logout
        client.auth.logout()
        ```
    """

    def __init__(self, http: HttpClient) -> None:
        """Initialize auth resource.

        Args:
            http: HTTP client instance.
        """
        super().__init__(http)

    def login(self, email: str, password: str) -> TokenResponse:
        """Login with email and password.

        Args:
            email: User email address.
            password: User password.

        Returns:
            TokenResponse with access and refresh tokens.

        Raises:
            AuthenticationError: If credentials are invalid.
        """
        data = self._http.post(
            "/auth/login",
            json={"email": email, "password": password},
        )
        return TokenResponse.model_validate(data)

    def logout(self) -> None:
        """Logout and invalidate current tokens.

        Note:
            This invalidates the current access token on the server.
            Local token cleanup should be done separately.
        """
        self._http.post("/auth/logout")

    def refresh(self, refresh_token: str) -> TokenResponse:
        """Refresh access token using refresh token.

        Args:
            refresh_token: Valid refresh token.

        Returns:
            TokenResponse with new access and refresh tokens.

        Raises:
            AuthenticationError: If refresh token is invalid or expired.
        """
        data = self._http.post(
            "/auth/refresh-token",
            json={"refresh_token": refresh_token},
        )
        return TokenResponse.model_validate(data)

    def status(self) -> UserInfo:
        """Get current authenticated user info.

        Returns:
            UserInfo for the currently authenticated user.

        Raises:
            AuthenticationError: If not authenticated.
        """
        data = self._http.get("/auth/me")
        return UserInfo.model_validate(data)

    def register(
        self,
        email: str,
        password: str,
        name: str | None = None,
    ) -> UserInfo:
        """Register a new user account.

        Args:
            email: Email address for the new account.
            password: Password for the new account.
            name: Optional display name.

        Returns:
            UserInfo for the newly created user.

        Raises:
            ValidationError: If email is already registered or input is invalid.
        """
        payload = {"email": email, "password": password}
        if name:
            payload["name"] = name

        data = self._http.post("/auth/register", json=payload)
        return UserInfo.model_validate(data)


class AsyncAuth:
    """Async authentication resource for JWT auth management."""

    def __init__(self, http) -> None:
        """Initialize async auth resource.

        Args:
            http: Async HTTP client instance.
        """
        self._http = http

    async def login(self, email: str, password: str) -> TokenResponse:
        """Login with email and password.

        Args:
            email: User email address.
            password: User password.

        Returns:
            TokenResponse with access and refresh tokens.
        """
        data = await self._http.post(
            "/auth/login",
            json={"email": email, "password": password},
        )
        return TokenResponse.model_validate(data)

    async def logout(self) -> None:
        """Logout and invalidate current tokens."""
        await self._http.post("/auth/logout")

    async def refresh(self, refresh_token: str) -> TokenResponse:
        """Refresh access token using refresh token.

        Args:
            refresh_token: Valid refresh token.

        Returns:
            TokenResponse with new access and refresh tokens.
        """
        data = await self._http.post(
            "/auth/refresh-token",
            json={"refresh_token": refresh_token},
        )
        return TokenResponse.model_validate(data)

    async def status(self) -> UserInfo:
        """Get current authenticated user info.

        Returns:
            UserInfo for the currently authenticated user.
        """
        data = await self._http.get("/auth/me")
        return UserInfo.model_validate(data)

    async def register(
        self,
        email: str,
        password: str,
        name: str | None = None,
    ) -> UserInfo:
        """Register a new user account.

        Args:
            email: Email address for the new account.
            password: Password for the new account.
            name: Optional display name.

        Returns:
            UserInfo for the newly created user.
        """
        payload = {"email": email, "password": password}
        if name:
            payload["name"] = name

        data = await self._http.post("/auth/register", json=payload)
        return UserInfo.model_validate(data)
