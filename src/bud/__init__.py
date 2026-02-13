"""
BudAI SDK - Official Python SDK for BudAI Platform.

Pipelines, Executions, and DAG orchestration made simple.
"""

from bud._version import __version__
from bud.client import AsyncBudClient, BudClient
from bud.dsl import Action, Pipeline
from bud.exceptions import (
    AuthenticationError,
    BudError,
    ConnectionError,
    ContentFilterError,
    ContextLengthError,
    ExecutionError,
    InferenceError,
    ModelNotFoundError,
    NotFoundError,
    RateLimitError,
    TimeoutError,
    ValidationError,
)
from bud.models.telemetry import (
    FilterCondition,
    FilterOperator,
    OrderBySpec,
    TelemetryErrorResponse,
    TelemetryQueryResponse,
    TelemetrySpanItem,
)

__all__ = [
    # Version
    "__version__",
    # Clients
    "BudClient",
    "AsyncBudClient",
    # DSL
    "Pipeline",
    "Action",
    # Exceptions
    "BudError",
    "AuthenticationError",
    "RateLimitError",
    "ValidationError",
    "NotFoundError",
    "ExecutionError",
    "ConnectionError",
    "TimeoutError",
    # Inference Exceptions
    "InferenceError",
    "ContentFilterError",
    "ContextLengthError",
    "ModelNotFoundError",
    # Telemetry / Observability
    "FilterCondition",
    "FilterOperator",
    "OrderBySpec",
    "TelemetryErrorResponse",
    "TelemetryQueryResponse",
    "TelemetrySpanItem",
]
