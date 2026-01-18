"""Base resource class."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bud._http import AsyncHttpClient, HttpClient


class SyncResource:
    """Base class for synchronous API resources."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http


class AsyncResource:
    """Base class for asynchronous API resources."""

    def __init__(self, http: AsyncHttpClient) -> None:
        self._http = http
