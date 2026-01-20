"""HTTP client infrastructure for BudAI SDK.

Handles:
- Authentication via AuthProvider
- Retries with exponential backoff
- Rate limit handling
- Error mapping
- Auto token refresh
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, TypeVar

import httpx

from bud._version import __version__
from bud.exceptions import (
    AuthenticationError,
    BudError,
    ConnectionError,
    NotFoundError,
    RateLimitError,
    TimeoutError,
    ValidationError,
)

if TYPE_CHECKING:
    from bud.auth import AuthProvider

T = TypeVar("T")

DEFAULT_HEADERS = {
    "User-Agent": f"bud-sdk-python/{__version__}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}


class HttpClient:
    """Synchronous HTTP client for BudAI API."""

    def __init__(
        self,
        base_url: str,
        auth: AuthProvider | None = None,
        timeout: float = 60.0,
        max_retries: int = 3,
        verify_ssl: bool = True,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth = auth
        self._timeout = timeout
        self._max_retries = max_retries

        self._client = httpx.Client(
            base_url=self._base_url,
            headers=DEFAULT_HEADERS.copy(),
            timeout=timeout,
            verify=verify_ssl,
        )

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        """Perform GET request."""
        return self._request("GET", path, params=params)

    def post(self, path: str, *, json: dict[str, Any] | None = None) -> Any:
        """Perform POST request."""
        return self._request("POST", path, json=json)

    def put(self, path: str, *, json: dict[str, Any] | None = None) -> Any:
        """Perform PUT request."""
        return self._request("PUT", path, json=json)

    def patch(self, path: str, *, json: dict[str, Any] | None = None) -> Any:
        """Perform PATCH request."""
        return self._request("PATCH", path, json=json)

    def delete(self, path: str) -> Any:
        """Perform DELETE request."""
        return self._request("DELETE", path)

    @contextmanager
    def stream(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> Iterator[httpx.Response]:
        """Stream HTTP response for SSE endpoints.

        Args:
            method: HTTP method (typically POST).
            path: API path.
            json: Request body as JSON.

        Yields:
            httpx.Response object for streaming iteration.

        Example:
            with client.stream("POST", "/v1/chat/completions", json=payload) as response:
                for line in response.iter_lines():
                    print(line)
        """
        # Ensure auth is valid before request
        self._ensure_auth()
        auth_headers = self._get_auth_headers()

        # Use extended timeouts for streaming LLM inference
        stream_timeout = httpx.Timeout(
            connect=10.0,  # Connection establishment
            read=600.0,  # 10 minutes for long completions
            write=30.0,  # Request body upload
            pool=5.0,  # Pool acquisition
        )

        with self._client.stream(
            method,
            path,
            json=json,
            headers={
                **auth_headers,
                "Accept": "text/event-stream",
            },
            timeout=stream_timeout,
        ) as response:
            # Check for errors before yielding
            if not response.is_success:
                # Read the response to get error details
                response.read()
                self._handle_response(response)
            yield response

    def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers from auth provider."""
        if self._auth is None:
            return {}
        return self._auth.get_headers()

    def _ensure_auth(self) -> None:
        """Ensure auth is valid, refreshing if needed."""
        if self._auth is None:
            return
        if self._auth.needs_refresh():
            self._auth.refresh(self._client)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        _auth_retry: bool = False,
    ) -> Any:
        """Perform HTTP request with retries and error handling."""
        last_exception: Exception | None = None
        retry_count = 0

        # Ensure auth is valid before request
        self._ensure_auth()

        while retry_count <= self._max_retries:
            try:
                # Get auth headers for this request
                auth_headers = self._get_auth_headers()

                response = self._client.request(
                    method,
                    path,
                    params=_filter_none(params) if params else None,
                    json=json,
                    headers=auth_headers,
                )
                return self._handle_response(response)

            except httpx.TimeoutException as e:
                last_exception = TimeoutError(f"Request timed out: {e}")
                retry_count += 1

            except httpx.ConnectError as e:
                last_exception = ConnectionError(f"Failed to connect: {e}")
                retry_count += 1

            except RateLimitError as e:
                # Use retry_after if available, otherwise exponential backoff
                wait_time = e.retry_after or (2**retry_count)
                time.sleep(wait_time)
                retry_count += 1
                last_exception = e

            except AuthenticationError:
                # Try to refresh and retry once
                if not _auth_retry and self._auth is not None:
                    try:
                        self._auth.refresh(self._client)
                        return self._request(
                            method, path, params=params, json=json, _auth_retry=True
                        )
                    except Exception:
                        pass
                raise

            except (ValidationError, NotFoundError):
                # Don't retry these
                raise

            except BudError:
                # Retry other BudErrors
                retry_count += 1

            if retry_count <= self._max_retries:
                # Exponential backoff
                time.sleep(2**retry_count * 0.1)

        if last_exception:
            raise last_exception
        raise BudError("Request failed after retries")

    def _handle_response(self, response: httpx.Response) -> Any:
        """Handle HTTP response and map errors."""
        if response.status_code == 204:
            return None

        try:
            data = response.json()
        except Exception:
            data = None

        if response.is_success:
            return data

        # Map HTTP errors to exceptions
        message = self._extract_error_message(data, response)

        if response.status_code == 401:
            raise AuthenticationError(message, response=response)

        if response.status_code == 404:
            raise NotFoundError(message, response=response)

        if response.status_code == 422:
            errors = data.get("errors", []) if isinstance(data, dict) else []
            raise ValidationError(message, errors=errors, response=response)

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            retry_after_int: int | None = None
            if retry_after:
                with contextlib.suppress(ValueError):
                    retry_after_int = int(retry_after)
            raise RateLimitError(
                message,
                retry_after=retry_after_int,
                response=response,
            )

        if response.status_code >= 500:
            raise BudError(f"Server error: {message}", response=response)

        raise BudError(message, response=response)

    def _extract_error_message(self, data: Any, response: httpx.Response) -> str:
        """Extract error message from response."""
        if isinstance(data, dict):
            if "message" in data:
                return data["message"]
            if "error" in data:
                error = data["error"]
                if isinstance(error, str):
                    return error
                if isinstance(error, dict) and "message" in error:
                    return error["message"]
            if "detail" in data:
                return str(data["detail"])

        return f"HTTP {response.status_code}: {response.reason_phrase}"


class AsyncHttpClient:
    """Asynchronous HTTP client for BudAI API."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout: float = 60.0,
        max_retries: int = 3,
        verify_ssl: bool = True,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                **DEFAULT_HEADERS,
                "Authorization": f"Bearer {api_key}",
            },
            timeout=timeout,
            verify=verify_ssl,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> AsyncHttpClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        """Perform GET request."""
        return await self._request("GET", path, params=params)

    async def post(self, path: str, *, json: dict[str, Any] | None = None) -> Any:
        """Perform POST request."""
        return await self._request("POST", path, json=json)

    async def put(self, path: str, *, json: dict[str, Any] | None = None) -> Any:
        """Perform PUT request."""
        return await self._request("PUT", path, json=json)

    async def patch(self, path: str, *, json: dict[str, Any] | None = None) -> Any:
        """Perform PATCH request."""
        return await self._request("PATCH", path, json=json)

    async def delete(self, path: str) -> Any:
        """Perform DELETE request."""
        return await self._request("DELETE", path)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        """Perform HTTP request with retries and error handling."""
        import anyio

        last_exception: Exception | None = None
        retry_count = 0

        while retry_count <= self._max_retries:
            try:
                response = await self._client.request(
                    method,
                    path,
                    params=_filter_none(params) if params else None,
                    json=json,
                )
                return self._handle_response(response)

            except httpx.TimeoutException as e:
                last_exception = TimeoutError(f"Request timed out: {e}")
                retry_count += 1

            except httpx.ConnectError as e:
                last_exception = ConnectionError(f"Failed to connect: {e}")
                retry_count += 1

            except RateLimitError as e:
                wait_time = e.retry_after or (2**retry_count)
                await anyio.sleep(wait_time)
                retry_count += 1
                last_exception = e

            except (AuthenticationError, ValidationError, NotFoundError):
                raise

            except BudError:
                retry_count += 1

            if retry_count <= self._max_retries:
                await anyio.sleep(2**retry_count * 0.1)

        if last_exception:
            raise last_exception
        raise BudError("Request failed after retries")

    def _handle_response(self, response: httpx.Response) -> Any:
        """Handle HTTP response and map errors."""
        if response.status_code == 204:
            return None

        try:
            data = response.json()
        except Exception:
            data = None

        if response.is_success:
            return data

        message = self._extract_error_message(data, response)

        if response.status_code == 401:
            raise AuthenticationError(message, response=response)

        if response.status_code == 404:
            raise NotFoundError(message, response=response)

        if response.status_code == 422:
            errors = data.get("errors", []) if isinstance(data, dict) else []
            raise ValidationError(message, errors=errors, response=response)

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            retry_after_int: int | None = None
            if retry_after:
                with contextlib.suppress(ValueError):
                    retry_after_int = int(retry_after)
            raise RateLimitError(
                message,
                retry_after=retry_after_int,
                response=response,
            )

        if response.status_code >= 500:
            raise BudError(f"Server error: {message}", response=response)

        raise BudError(message, response=response)

    def _extract_error_message(self, data: Any, response: httpx.Response) -> str:
        """Extract error message from response."""
        if isinstance(data, dict):
            if "message" in data:
                return data["message"]
            if "error" in data:
                error = data["error"]
                if isinstance(error, str):
                    return error
                if isinstance(error, dict) and "message" in error:
                    return error["message"]
            if "detail" in data:
                return str(data["detail"])

        return f"HTTP {response.status_code}: {response.reason_phrase}"


def _filter_none(params: dict[str, Any]) -> dict[str, Any]:
    """Remove None values from params dict."""
    return {k: v for k, v in params.items() if v is not None}
