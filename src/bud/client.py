"""BudAI SDK Client.

Main entry point for interacting with the BudAI API.
"""

from __future__ import annotations

import os
from typing import Any

from bud._config import BudConfig
from bud._http import AsyncHttpClient, HttpClient
from bud.auth import APIKeyAuth, AuthProvider, DaprAuth, JWTAuth
from bud.exceptions import AuthenticationError
from bud.resources.actions import Actions, AsyncActions
from bud.resources.audit import AsyncAudit, Audit
from bud.resources.auth import AsyncAuth, Auth
from bud.resources.benchmarks import AsyncBenchmarks, Benchmarks
from bud.resources.clusters import AsyncClusters, Clusters
from bud.resources.events import AsyncEvents, Events
from bud.resources.executions import AsyncExecutions, Executions
from bud.resources.inference import Chat, Classifications, Embeddings, InferenceModels
from bud.resources.pipelines import AsyncPipelines, Pipelines
from bud.resources.schedules import AsyncSchedules, Schedules
from bud.resources.webhooks import AsyncWebhooks, Webhooks

# Dapr invoke path prefix for internal service calls
DAPR_APP_ID = "budpipeline"
DAPR_INVOKE_PREFIX = f"/v1.0/invoke/{DAPR_APP_ID}/method"
DAPR_DEFAULT_SIDECAR = "http://localhost:3500"


class BudClient:
    """Synchronous client for BudAI API.

    Supports multiple authentication methods:
    - API key: Simple token-based auth
    - Dapr token: For internal service-to-service calls
    - Email/password: JWT-based auth with auto token refresh

    Example:
        ```python
        from bud import BudClient

        # Using API key
        client = BudClient(api_key="your-api-key")

        # Using Dapr token (internal services)
        client = BudClient(dapr_token="your-dapr-token", user_id="user-123")

        # Using email/password (JWT auth)
        client = BudClient(email="user@example.com", password="secret")

        # List pipelines
        pipelines = client.pipelines.list()

        # Run a pipeline
        execution = client.executions.run("pipeline-id", params={"key": "value"})
        ```

    Environment variables:
        BUD_API_KEY: API key
        BUD_DAPR_TOKEN: Dapr token for internal auth
        BUD_USER_ID: User ID for Dapr auth
        BUD_EMAIL: Email for JWT auth
        BUD_PASSWORD: Password for JWT auth
        BUD_BASE_URL: Base URL (default: https://api.bud.io)
        BUD_TIMEOUT: Request timeout in seconds (default: 60)
        BUD_MAX_RETRIES: Max retries (default: 3)

    Auth priority (highest to lowest):
        1. Explicit `auth` parameter
        2. Explicit credential parameters (api_key, dapr_token, email/password)
        3. Environment variables
        4. Config file
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        email: str | None = None,
        password: str | None = None,
        dapr_token: str | None = None,
        user_id: str | None = None,
        auth: AuthProvider | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        verify_ssl: bool | None = None,
    ) -> None:
        """Initialize the BudAI client.

        Args:
            api_key: API key for token-based auth.
            email: Email for JWT auth (requires password).
            password: Password for JWT auth (requires email).
            dapr_token: Dapr token for internal service auth.
            user_id: User ID for Dapr auth (optional).
            auth: Explicit AuthProvider instance to use.
            base_url: API base URL. Falls back to BUD_BASE_URL env var.
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retries for failed requests.
            verify_ssl: Whether to verify SSL certificates.
        """
        # Load config with defaults
        config = BudConfig.load()

        # Resolve base URL (may be overridden for Dapr below)
        self._base_url = base_url or os.environ.get("BUD_BASE_URL") or config.base_url
        self._timeout = timeout if timeout is not None else config.timeout
        self._max_retries = max_retries if max_retries is not None else config.max_retries
        self._verify_ssl = verify_ssl if verify_ssl is not None else config.verify_ssl

        # Resolve authentication
        self._auth = self._resolve_auth(
            api_key=api_key,
            email=email,
            password=password,
            dapr_token=dapr_token,
            user_id=user_id,
            auth=auth,
            config=config,
        )

        # For Dapr auth:
        # - Default to localhost:3500 sidecar if no base_url specified
        # - Append the invoke prefix to base URL
        # This transforms: http://localhost:3500
        # Into: http://localhost:3500/v1.0/invoke/budpipeline/method
        effective_base_url = self._base_url
        if isinstance(self._auth, DaprAuth):
            # Use default Dapr sidecar if no explicit URL provided
            if not base_url and not os.environ.get("BUD_BASE_URL"):
                effective_base_url = DAPR_DEFAULT_SIDECAR
            effective_base_url = f"{effective_base_url.rstrip('/')}{DAPR_INVOKE_PREFIX}"

        # Initialize HTTP client
        self._http = HttpClient(
            base_url=effective_base_url,
            auth=self._auth,
            timeout=self._timeout,
            max_retries=self._max_retries,
            verify_ssl=self._verify_ssl,
        )

        # Initialize resource managers
        self.auth = Auth(self._http)
        self.pipelines = Pipelines(self._http)
        self.executions = Executions(self._http)
        self.schedules = Schedules(self._http)
        self.webhooks = Webhooks(self._http)
        self.events = Events(self._http)
        self.actions = Actions(self._http)
        self.benchmarks = Benchmarks(self._http)
        self.clusters = Clusters(self._http)
        self.audit = Audit(self._http)

        # OpenAI-compatible inference resources
        self.chat = Chat(self._http)
        self.embeddings = Embeddings(self._http)
        self.classifications = Classifications(self._http)
        self.models = InferenceModels(self._http)

    def _resolve_auth(
        self,
        api_key: str | None = None,
        email: str | None = None,
        password: str | None = None,
        dapr_token: str | None = None,
        user_id: str | None = None,
        auth: AuthProvider | None = None,
        config: BudConfig | None = None,
    ) -> AuthProvider:
        """Resolve authentication provider from parameters, environment, and config.

        Priority order:
        1. Explicit auth provider
        2. Explicit api_key
        3. Explicit dapr_token
        4. Explicit email/password
        5. BUD_API_KEY env var
        6. BUD_DAPR_TOKEN env var
        7. BUD_EMAIL/BUD_PASSWORD env vars
        8. Config file (api_key or [auth] section)

        Returns:
            Resolved AuthProvider instance.

        Raises:
            ValueError: If no authentication credentials are provided.
        """
        # 1. Use explicit auth provider if provided
        if auth is not None:
            return auth

        # 2. Check explicit API key (highest priority among credentials)
        if api_key:
            return APIKeyAuth(api_key=api_key)

        # 3. Check explicit Dapr token
        if dapr_token:
            return DaprAuth(token=dapr_token, user_id=user_id)

        # 4. Check explicit email/password
        if email and password:
            return JWTAuth(email=email, password=password)

        # 5. Check BUD_API_KEY env var
        env_api_key = os.environ.get("BUD_API_KEY")
        if env_api_key:
            return APIKeyAuth(api_key=env_api_key)

        # 6. Check BUD_DAPR_TOKEN env var
        env_dapr_token = os.environ.get("BUD_DAPR_TOKEN")
        if env_dapr_token:
            env_user_id = user_id or os.environ.get("BUD_USER_ID")
            return DaprAuth(token=env_dapr_token, user_id=env_user_id)

        # 7. Check BUD_EMAIL/BUD_PASSWORD env vars
        env_email = os.environ.get("BUD_EMAIL")
        env_password = os.environ.get("BUD_PASSWORD")
        if env_email and env_password:
            return JWTAuth(email=env_email, password=env_password)

        # 8. Check config file
        if config:
            # Top-level api_key takes priority
            if config.api_key:
                return APIKeyAuth(api_key=config.api_key)

            # Check [auth] section
            auth_cfg = config.auth
            if auth_cfg.type == "dapr" and auth_cfg.dapr_token:
                return DaprAuth(token=auth_cfg.dapr_token, user_id=auth_cfg.user_id)
            if auth_cfg.type == "jwt" and auth_cfg.email and auth_cfg.password:
                return JWTAuth(email=auth_cfg.email, password=auth_cfg.password)
            if auth_cfg.type == "api_key" and auth_cfg.api_key:
                return APIKeyAuth(api_key=auth_cfg.api_key)

        # 9. Check stored tokens from CLI login (~/.bud/tokens.json)
        tokens = self._load_stored_tokens()
        if tokens and tokens.get("access_token"):
            jwt_auth = JWTAuth(email="", password="")
            jwt_auth._access_token = tokens["access_token"]
            jwt_auth._refresh_token = tokens.get("refresh_token")
            jwt_auth._expires_at = tokens.get("expires_at", 0)
            return jwt_auth

        # No auth credentials found
        raise ValueError(
            "No authentication credentials provided. "
            "Provide one of: api_key, dapr_token, email/password, or auth provider. "
            "Or set environment variables: BUD_API_KEY, BUD_DAPR_TOKEN, or BUD_EMAIL/BUD_PASSWORD."
        )

    def _load_stored_tokens(self) -> dict[str, Any] | None:
        """Load stored tokens from CLI login."""
        import json
        from pathlib import Path

        tokens_file = Path.home() / ".bud" / "tokens.json"
        if tokens_file.exists():
            try:
                with open(tokens_file) as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def close(self) -> None:
        """Close the client and release resources."""
        self._http.close()

    def __enter__(self) -> BudClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"BudClient(base_url={self._base_url!r})"

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def api_key(self) -> str | None:
        if isinstance(self._auth, APIKeyAuth):
            return self._auth.api_key
        return None


class AsyncBudClient:
    """Asynchronous client for BudAI API.

    Example:
        ```python
        import asyncio
        from bud import AsyncBudClient

        async def main():
            async with AsyncBudClient(api_key="your-api-key") as client:
                # List pipelines
                pipelines = await client.pipelines.list()

                # Run a pipeline
                execution = await client.executions.run(
                    "pipeline-id",
                    params={"key": "value"}
                )

        asyncio.run(main())
        ```
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        verify_ssl: bool | None = None,
    ) -> None:
        """Initialize the async BudAI client.

        Args:
            api_key: API key. Falls back to BUD_API_KEY env var or config file.
            base_url: API base URL. Falls back to BUD_API_URL env var.
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retries for failed requests.
            verify_ssl: Whether to verify SSL certificates.
        """
        # Load config with defaults
        config = BudConfig.load()

        # Override with explicit arguments
        self._api_key = api_key or config.api_key
        self._base_url = base_url or config.base_url
        self._timeout = timeout if timeout is not None else config.timeout
        self._max_retries = max_retries if max_retries is not None else config.max_retries
        self._verify_ssl = verify_ssl if verify_ssl is not None else config.verify_ssl

        if not self._api_key:
            raise AuthenticationError(
                "API key is required. Set BUD_API_KEY environment variable, "
                "pass api_key argument, or configure in ~/.bud/config.toml"
            )

        # Initialize HTTP client
        self._http = AsyncHttpClient(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=self._timeout,
            max_retries=self._max_retries,
            verify_ssl=self._verify_ssl,
        )

        # Initialize resource managers
        self.auth = AsyncAuth(self._http)
        self.pipelines = AsyncPipelines(self._http)
        self.executions = AsyncExecutions(self._http)
        self.schedules = AsyncSchedules(self._http)
        self.webhooks = AsyncWebhooks(self._http)
        self.events = AsyncEvents(self._http)
        self.actions = AsyncActions(self._http)
        self.benchmarks = AsyncBenchmarks(self._http)
        self.clusters = AsyncClusters(self._http)
        self.audit = AsyncAudit(self._http)

    async def close(self) -> None:
        """Close the client and release resources."""
        await self._http.close()

    async def __aenter__(self) -> AsyncBudClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    def __repr__(self) -> str:
        return f"AsyncBudClient(base_url={self._base_url!r})"

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def api_key(self) -> str | None:
        return self._api_key
