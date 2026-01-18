"""Authentication providers for BudAI SDK.

Supports multiple authentication methods:
- JWT: OAuth2/JWT for public API users (email/password login)
- Dapr: Service-to-service authentication via Dapr token
- APIKey: Simple API key authentication
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import httpx


class AuthProvider(ABC):
    """Base authentication provider interface.

    All authentication methods must implement this interface.
    """

    @abstractmethod
    def get_headers(self) -> dict[str, str]:
        """Return authentication headers for requests.

        Returns:
            Dictionary of headers to include in requests.
        """
        ...

    @abstractmethod
    def needs_refresh(self) -> bool:
        """Check if credentials need refreshing.

        Returns:
            True if credentials should be refreshed before next request.
        """
        ...

    @abstractmethod
    def refresh(self, client: httpx.Client) -> None:
        """Refresh credentials if needed.

        Args:
            client: HTTP client to use for refresh requests.
        """
        ...

    @property
    @abstractmethod
    def is_authenticated(self) -> bool:
        """Check if currently authenticated.

        Returns:
            True if valid credentials are available.
        """
        ...


@dataclass
class JWTAuth(AuthProvider):
    """JWT authentication for public API users.

    Authenticates via email/password and manages JWT token lifecycle.

    Example:
        ```python
        auth = JWTAuth(email="user@example.com", password="secret")
        # Login is performed automatically on first request or manually:
        auth.login(http_client)
        ```

    Attributes:
        email: User email for authentication.
        password: User password for authentication.
    """

    email: str
    password: str = field(repr=False)  # Never log passwords
    _access_token: str | None = field(default=None, repr=False)
    _refresh_token: str | None = field(default=None, repr=False)
    _expires_at: float = field(default=0.0, repr=False)
    _refresh_buffer: int = field(default=60, repr=False)  # Refresh 60s before expiry

    def get_headers(self) -> dict[str, str]:
        """Return JWT Bearer token header.

        Returns:
            Dict with Authorization header if authenticated, empty dict otherwise.
        """
        if self._access_token:
            return {"Authorization": f"Bearer {self._access_token}"}
        return {}

    def needs_refresh(self) -> bool:
        """Check if token needs refreshing.

        Returns:
            True if not authenticated or token is close to expiry.
        """
        if not self._access_token:
            return True
        return time.time() >= (self._expires_at - self._refresh_buffer)

    @property
    def is_authenticated(self) -> bool:
        """Check if we have a valid, non-expired token.

        Returns:
            True if access token exists and hasn't expired.
        """
        return self._access_token is not None and time.time() < self._expires_at

    def login(self, client: Any, base_url: str | None = None) -> dict[str, Any]:
        """Perform initial login to get tokens.

        Args:
            client: HTTP client to use for login request.
            base_url: Optional base URL for login endpoint (for standalone httpx.Client).

        Returns:
            Login response data containing tokens.

        Raises:
            httpx.HTTPStatusError: If login fails.
        """
        url = "/auth/login"
        if base_url:
            url = f"{base_url.rstrip('/')}{url}"

        response = client.post(
            url,
            json={"email": self.email, "password": self.password},
        )
        response.raise_for_status()
        data = response.json()

        # Handle nested token response (API returns tokens under 'token' key)
        token_data = data.get("token", data)

        self._access_token = token_data.get("access_token")
        self._refresh_token = token_data.get("refresh_token")

        # Calculate expiry (default 1 hour if not provided)
        expires_in = token_data.get("expires_in", 3600)
        self._expires_at = time.time() + expires_in

        return data

    def refresh(self, client: Any, base_url: str | None = None) -> None:
        """Refresh the access token.

        If refresh token is available, uses it to get new tokens.
        If refresh fails with 401, performs full re-login.

        Args:
            client: HTTP client to use for refresh request.
            base_url: Optional base URL for refresh endpoint (for standalone httpx.Client).
        """
        if not self._refresh_token:
            # No refresh token, need to re-login
            self.login(client, base_url)
            return

        url = "/auth/refresh-token"
        if base_url:
            url = f"{base_url.rstrip('/')}{url}"

        response = client.post(
            url,
            json={"refresh_token": self._refresh_token},
        )

        if response.status_code == 401:
            # Refresh token expired, re-login
            self.login(client, base_url)
            return

        response.raise_for_status()
        data = response.json()

        # Handle nested token response
        token_data = data.get("token", data)

        self._access_token = token_data.get("access_token")
        if "refresh_token" in token_data:
            self._refresh_token = token_data["refresh_token"]

        expires_in = token_data.get("expires_in", 3600)
        self._expires_at = time.time() + expires_in

    def logout(self, client: Any) -> None:
        """Logout and invalidate tokens.

        Args:
            client: HTTP client to use for logout request.
        """
        if self._access_token:
            try:
                client.post(
                    "/auth/logout",
                    headers=self.get_headers(),
                )
            except Exception:
                pass  # Best effort logout

        self._access_token = None
        self._refresh_token = None
        self._expires_at = 0.0


@dataclass
class DaprAuth(AuthProvider):
    """Dapr token authentication for internal services.

    Used for service-to-service communication within the Dapr ecosystem.

    Example:
        ```python
        auth = DaprAuth(token="your-dapr-token", user_id="user-123")
        client = BudClient(auth=auth)
        ```

    Attributes:
        token: Dapr API token for authentication.
        user_id: Optional user ID for scoping requests.
    """

    token: str = field(repr=False)  # Never log tokens
    user_id: str | None = None

    def get_headers(self) -> dict[str, str]:
        """Return Dapr authentication headers.

        Returns:
            Dict with dapr-api-token and optionally X-User-ID headers.
        """
        headers = {"dapr-api-token": self.token}
        if self.user_id:
            headers["X-User-ID"] = self.user_id
        return headers

    def needs_refresh(self) -> bool:
        """Dapr tokens don't expire in the same way.

        Returns:
            Always False.
        """
        return False

    def refresh(self, client: Any) -> None:
        """No refresh needed for Dapr tokens.

        Args:
            client: HTTP client (unused).
        """
        pass

    @property
    def is_authenticated(self) -> bool:
        """Check if token is present.

        Returns:
            True if token is non-empty.
        """
        return bool(self.token)


@dataclass
class APIKeyAuth(AuthProvider):
    """Simple API key authentication.

    For programmatic access without user credentials.

    Example:
        ```python
        auth = APIKeyAuth(api_key="bud_sk_...")
        client = BudClient(auth=auth)
        ```

    Attributes:
        api_key: API key for authentication.
    """

    api_key: str = field(repr=False)  # Never log API keys

    def get_headers(self) -> dict[str, str]:
        """Return API key header.

        Returns:
            Dict with Authorization Bearer header.
        """
        return {"Authorization": f"Bearer {self.api_key}"}

    def needs_refresh(self) -> bool:
        """API keys don't expire.

        Returns:
            Always False.
        """
        return False

    def refresh(self, client: Any) -> None:
        """No refresh needed for API keys.

        Args:
            client: HTTP client (unused).
        """
        pass

    @property
    def is_authenticated(self) -> bool:
        """Check if API key is present.

        Returns:
            True if api_key is non-empty.
        """
        return bool(self.api_key)
