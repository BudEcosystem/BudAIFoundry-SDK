"""BudAI SDK exceptions.

All exceptions inherit from BudError for easy catching.
"""

from __future__ import annotations

from typing import Any


class BudError(Exception):
    """Base exception for all BudAI SDK errors."""

    def __init__(self, message: str, *, response: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.response = response

    def __str__(self) -> str:
        return self.message

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.message!r})"


class AuthenticationError(BudError):
    """Invalid or missing API key.

    Check that BUD_API_KEY is set or pass api_key to BudClient.
    """


class RateLimitError(BudError):
    """Rate limit exceeded.

    Check retry_after for when to retry.
    """

    def __init__(
        self, message: str, *, retry_after: int | None = None, response: Any = None
    ) -> None:
        super().__init__(message, response=response)
        self.retry_after = retry_after


class ValidationError(BudError):
    """DAG or parameter validation failed.

    Check errors for detailed validation failures.
    """

    def __init__(
        self, message: str, *, errors: list[dict[str, Any]] | None = None, response: Any = None
    ) -> None:
        super().__init__(message, response=response)
        self.errors = errors or []


class NotFoundError(BudError):
    """Resource not found.

    The requested pipeline, execution, or other resource does not exist.
    """

    def __init__(
        self, message: str, *, resource_type: str = "", resource_id: str = "", response: Any = None
    ) -> None:
        super().__init__(message, response=response)
        self.resource_type = resource_type
        self.resource_id = resource_id


class ExecutionError(BudError):
    """Pipeline execution failed.

    Check execution_id and status for details.
    """

    def __init__(
        self,
        message: str,
        *,
        execution_id: str | None = None,
        status: str | None = None,
        response: Any = None,
    ) -> None:
        super().__init__(message, response=response)
        self.execution_id = execution_id
        self.status = status


class ConnectionError(BudError):
    """Failed to connect to BudAI API.

    Check network connectivity and base_url configuration.
    """


class TimeoutError(BudError):
    """Request timed out.

    Consider increasing the timeout or using async client.
    """
