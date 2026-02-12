# Plan: Add Telemetry Query API to BudAI SDK

## Overview

Add `client.observability.query(...)` to the BudAI SDK, connecting to the budapp `/prompts/telemetry/query` endpoint at a **different base URL** than the existing gateway. Uses a lazy-initialized second `HttpClient` sharing the same `AuthProvider`.

**API contract:** `POST <app_url>/prompts/telemetry/query` with `Authorization: Bearer <api_key>`.

---

## Architecture Decision

**Pattern:** Single client with internal dual HTTP clients (Stripe/OpenAI style).

- User-facing API unchanged; new `app_url` keyword-only param with `None` default
- Lazy second `HttpClient` created on first `client.observability` access
- Same `AuthProvider` instance shared across both HTTP clients
- Independent connection pools (httpx pools are per-host; no contention)
- App service downtime cannot affect gateway operations

**Why not other approaches:**
- Separate client class: breaks the unified SDK feel, forces users to manage two objects
- Transport mounts / absolute URLs: requires modifying all existing resource code
- URL derivation: magic behavior, fragile across environments

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `src/bud/models/telemetry.py` | **CREATE** | Pydantic models for request/response |
| `src/bud/resources/observability.py` | **CREATE** | Observability resource (sync + async) |
| `src/bud/client.py` | MODIFY | Add `app_url` param, lazy `_app_http`, `observability` property |
| `src/bud/_config.py` | MODIFY | Add `app_url` field to `BudConfig` |
| `src/bud/__init__.py` | MODIFY | Export new models |
| `tests/unit/test_telemetry/` | **CREATE** | Unit tests |
| `examples/observability/query_telemetry.py` | **CREATE** | Usage example for observability.query |

---

## Step 1: Pydantic Models -- `src/bud/models/telemetry.py`

Mirror the budapp schemas from `services/budapp/budapp/prompt_ops/schemas.py` (lines 1029-1114), **client-side only** (exclude `project_id` which is server-injected).

**Key differences from budmetrics schemas:** budapp uses `page` (1-based) + `limit` pagination, and `TelemetryQueryResponse` extends `PaginatedSuccessResponse` with `page`, `limit`, `total_record` fields.

```python
"""Pydantic models for the telemetry query API."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class FilterOperator(str, Enum):
    eq = "eq"
    neq = "neq"
    gt = "gt"
    gte = "gte"
    lt = "lt"
    lte = "lte"
    in_ = "in_"
    not_in = "not_in"
    like = "like"
    is_null = "is_null"
    is_not_null = "is_not_null"


class FilterCondition(BaseModel):
    field: str = Field(..., min_length=1, max_length=200)
    op: FilterOperator
    value: Any = None


class OrderBySpec(BaseModel):
    field: str
    direction: Literal["asc", "desc"] = "desc"


class TelemetrySpanItem(BaseModel):
    timestamp: str
    trace_id: str
    span_id: str
    parent_span_id: str = ""
    trace_state: str = ""
    span_name: str
    span_kind: str = ""
    service_name: str = ""
    scope_name: str = ""
    scope_version: str = ""
    duration: int = 0
    status_code: str = ""
    status_message: str = ""
    child_count: int = 0
    children: list[TelemetrySpanItem] = Field(default_factory=list)
    attributes: dict[str, str] = Field(default_factory=dict)
    resource_attributes: dict[str, str] | None = None
    events: list[dict[str, Any]] | None = None
    links: list[dict[str, Any]] | None = None


class TelemetryQueryResponse(BaseModel):
    object: str = "telemetry_query"
    data: list[TelemetrySpanItem] = Field(default_factory=list)
    page: int = 1
    limit: int = 10
    total_record: int = 0
    has_more: bool = False
    code: int = 200
    message: str | None = None


class TelemetryErrorResponse(BaseModel):
    object: str = "error"
    code: int = 500
    message: str | None = None
    type: str | None = "InternalServerError"
    param: str | None = None
```

**Error handling:** The SDK's `HttpClient._handle_response()` (line 250 in `_http.py`) already
maps budapp's `ErrorResponse` to SDK exceptions automatically:
- `401` -> `AuthenticationError` (invalid API key)
- `404` -> `NotFoundError` (prompt not found)
- `422` -> `ValidationError` (bad request body)
- `429` -> `RateLimitError`
- `500` -> `BudError("Server error: Failed to query telemetry")`

The error `message` field is extracted from the JSON body. No additional error handling
is needed in the `Observability` resource -- it relies on the existing HTTP layer.

---

## Step 2: Observability Resource -- `src/bud/resources/observability.py`

Follow the existing resource pattern from `src/bud/resources/_base.py`. Both sync and async variants. Named `Observability` so future observability features (metrics queries, trace details, etc.) can be added here.

```python
"""Observability resource for the BudAI SDK."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from bud.models.telemetry import (
    FilterCondition,
    OrderBySpec,
    TelemetryQueryResponse,
)
from bud.resources._base import AsyncResource, SyncResource

if TYPE_CHECKING:
    from bud._http import AsyncHttpClient, HttpClient


class Observability(SyncResource):
    """Query observability data from the BudAI app service."""

    def query(
        self,
        prompt_id: str,
        from_date: datetime,
        *,
        version: str | None = None,
        to_date: datetime | None = None,
        trace_id: str | None = None,
        span_names: list[str] | None = None,
        depth: int = 0,
        select_attributes: list[str] | None = None,
        include_all_attributes: bool = False,
        include_resource_attributes: bool = False,
        include_events: bool = False,
        include_links: bool = False,
        span_filters: list[FilterCondition] | None = None,
        resource_filters: list[FilterCondition] | None = None,
        order_by: list[OrderBySpec] | None = None,
        page: int = 1,
        limit: int = 10,
    ) -> TelemetryQueryResponse:
        payload: dict[str, Any] = {
            "prompt_id": prompt_id,
            "from_date": from_date.isoformat(),
        }
        if version is not None:
            payload["version"] = version
        if to_date is not None:
            payload["to_date"] = to_date.isoformat()
        if trace_id is not None:
            payload["trace_id"] = trace_id
        if span_names is not None:
            payload["span_names"] = span_names
        if depth != 0:
            payload["depth"] = depth
        if select_attributes is not None:
            payload["select_attributes"] = select_attributes
        if include_all_attributes:
            payload["include_all_attributes"] = True
        if include_resource_attributes:
            payload["include_resource_attributes"] = True
        if include_events:
            payload["include_events"] = True
        if include_links:
            payload["include_links"] = True
        if span_filters is not None:
            payload["span_filters"] = [f.model_dump() for f in span_filters]
        if resource_filters is not None:
            payload["resource_filters"] = [f.model_dump() for f in resource_filters]
        if order_by is not None:
            payload["order_by"] = [o.model_dump() for o in order_by]
        if page != 1:
            payload["page"] = page
        if limit != 10:
            payload["limit"] = limit

        data = self._http.post("/prompts/telemetry/query", json=payload)
        return TelemetryQueryResponse.model_validate(data)


class AsyncObservability(AsyncResource):
    """Async observability query resource."""

    async def query(
        self,
        prompt_id: str,
        from_date: datetime,
        *,
        version: str | None = None,
        to_date: datetime | None = None,
        trace_id: str | None = None,
        span_names: list[str] | None = None,
        depth: int = 0,
        select_attributes: list[str] | None = None,
        include_all_attributes: bool = False,
        include_resource_attributes: bool = False,
        include_events: bool = False,
        include_links: bool = False,
        span_filters: list[FilterCondition] | None = None,
        resource_filters: list[FilterCondition] | None = None,
        order_by: list[OrderBySpec] | None = None,
        page: int = 1,
        limit: int = 10,
    ) -> TelemetryQueryResponse:
        payload: dict[str, Any] = {
            "prompt_id": prompt_id,
            "from_date": from_date.isoformat(),
        }
        if version is not None:
            payload["version"] = version
        if to_date is not None:
            payload["to_date"] = to_date.isoformat()
        if trace_id is not None:
            payload["trace_id"] = trace_id
        if span_names is not None:
            payload["span_names"] = span_names
        if depth != 0:
            payload["depth"] = depth
        if select_attributes is not None:
            payload["select_attributes"] = select_attributes
        if include_all_attributes:
            payload["include_all_attributes"] = True
        if include_resource_attributes:
            payload["include_resource_attributes"] = True
        if include_events:
            payload["include_events"] = True
        if include_links:
            payload["include_links"] = True
        if span_filters is not None:
            payload["span_filters"] = [f.model_dump() for f in span_filters]
        if resource_filters is not None:
            payload["resource_filters"] = [f.model_dump() for f in resource_filters]
        if order_by is not None:
            payload["order_by"] = [o.model_dump() for o in order_by]
        if page != 1:
            payload["page"] = page
        if limit != 10:
            payload["limit"] = limit

        data = await self._http.post("/prompts/telemetry/query", json=payload)
        return TelemetryQueryResponse.model_validate(data)
```

---

## Step 3: Config -- `src/bud/_config.py`

Add `app_url` field with env var `BUD_APP_URL`.

```python
# In BudConfig dataclass (line ~47):
app_url: str | None = None

# In from_env() (line ~63):
app_url=os.getenv("BUD_APP_URL"),

# In from_file() (line ~95):
app_url=data.get("app_url"),

# In load() (line ~107), add after verify_ssl override:
if os.getenv("BUD_APP_URL"):
    config.app_url = env_config.app_url
```

---

## Step 4: Client -- `src/bud/client.py`

### BudClient changes

```python
# __init__ signature: add keyword-only param
def __init__(
    self,
    api_key: str | None = None,
    *,
    ...existing params...,
    app_url: str | None = None,        # NEW
    app_timeout: float | None = None,   # NEW
) -> None:

# In __init__ body, after auth resolution:
self._app_url = app_url or os.environ.get("BUD_APP_URL") or (config.app_url if config else None)
self._app_timeout = app_timeout if app_timeout is not None else 30.0
self.__app_http: HttpClient | None = None  # lazy
self._observability: Observability | None = None   # lazy

# Lazy app HTTP client property:
@property
def _app_http(self) -> HttpClient:
    if self.__app_http is None:
        if not self._app_url:
            raise BudError(
                "App service URL not configured. "
                "Set BUD_APP_URL environment variable or pass app_url to BudClient()."
            )
        self.__app_http = HttpClient(
            base_url=self._app_url,
            auth=self._auth,
            timeout=self._app_timeout,
            max_retries=self._max_retries,
            verify_ssl=self._verify_ssl,
        )
    return self.__app_http

# Lazy observability resource property:
@property
def observability(self) -> Observability:
    if self._observability is None:
        self._observability = Observability(self._app_http)
    return self._observability

# Update close():
def close(self) -> None:
    self._http.close()
    if self.__app_http is not None:
        self.__app_http.close()
```

### AsyncBudClient changes

Same pattern with `AsyncHttpClient` and `AsyncObservability`:

```python
# __init__: add app_url, app_timeout params
# Lazy _app_http property creates AsyncHttpClient
# Lazy observability property creates AsyncObservability
# close(): also close __app_http if created
```

**Key difference:** `AsyncHttpClient.__init__` takes `api_key` directly (not `AuthProvider`), so pass `self._api_key` to it.

---

## Step 5: Exports -- `src/bud/__init__.py`

Add to exports:
```python
from bud.models.telemetry import (
    FilterCondition,
    FilterOperator,
    OrderBySpec,
    TelemetryErrorResponse,
    TelemetryQueryResponse,
    TelemetrySpanItem,
)
```

---

## Step 6: Tests -- `tests/unit/test_telemetry/`

### `tests/unit/test_telemetry/__init__.py`
Empty.

### `tests/unit/test_telemetry/test_models.py`
- Test `TelemetryQueryResponse.model_validate()` with sample server response
- Test `TelemetrySpanItem` recursive children parsing
- Test `FilterCondition` / `OrderBySpec` serialization

### `tests/unit/test_telemetry/test_resource.py`
Using `respx` to mock HTTP:
- `test_query_basic` -- minimal params, verify POST to `/prompts/telemetry/query`
- `test_query_all_params` -- all optional params, verify JSON payload
- `test_query_returns_typed_response` -- verify `TelemetryQueryResponse` type
- `test_query_auth_header` -- verify `Authorization: Bearer` header sent
- `test_query_error_401` -- `AuthenticationError`
- `test_query_error_404` -- `NotFoundError`
- `test_query_error_500` -- `BudError`
- `test_query_error_422` -- `ValidationError`
- `test_app_url_not_configured_raises` -- `BudError`
- `test_lazy_initialization` -- `_app_http` not created until `observability` accessed
- `test_close_cleans_up_app_http` -- both HTTP clients closed

### `tests/unit/test_telemetry/test_async_resource.py`
Async variants of the above tests.

---

## Step 7: Example -- `examples/observability/query_telemetry.py`

Usage example showing basic query, filtered query, pagination, and trace lookup.

---

## Edge Cases & Failure Modes

| Scenario | Behavior |
|----------|----------|
| `app_url` not set, `client.observability` accessed | `BudError` with actionable message |
| `app_url` set, budapp down | `ConnectionError` (gateway unaffected) |
| API key invalid for budapp | `AuthenticationError` (same exception type) |
| JWT auth with budapp | Works -- `JWTAuth.refresh()` updates token, both clients see it |
| Dapr auth with budapp | Works -- Dapr token sent as `dapr-api-token` header |
| `close()` before observability used | No-op for app HTTP client (never created) |
| Concurrent `client.observability` access | Safe -- Python GIL prevents race on property |

---

## Verification

```bash
cd /home/budadmin/varunsr/BudAIFoundry-SDK

# 1. Type checking
uv run mypy src/bud --ignore-missing-imports

# 2. Linting
uv run ruff check src/ tests/

# 3. All tests pass (existing + new)
uv run pytest tests/ -v

# 4. Manual smoke test (if dev server available)
python -c "
from bud import BudClient
client = BudClient(api_key='test-key', app_url='https://app.dev.bud.studio')
from datetime import datetime, timezone
result = client.observability.query(
    prompt_id='my-prompt',
    from_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
)
print(result)
"
```
