# Specification: SDK Observability Query API

## 1. Purpose

Add `client.observability.query(...)` to the BudAI Python SDK, enabling customers to query OpenTelemetry span data collected by the platform. The endpoint lives on the **budapp** service (not the gateway), requiring a second base URL.

## 2. API Surface

### 2.1 Client Configuration

```python
from bud import BudClient

client = BudClient(
    api_key="bud-...",
    base_url="https://gateway.bud.studio",   # existing -- for inference
    app_url="https://app.bud.studio",         # NEW -- for observability queries
)
```

| Parameter | Type | Default | Env Var | Description |
|-----------|------|---------|---------|-------------|
| `app_url` | `str \| None` | `None` | `BUD_APP_URL` | Base URL for the budapp service |
| `app_timeout` | `float \| None` | `30.0` | -- | HTTP timeout for app service requests |

If `app_url` is not set and `client.observability` is accessed, a `BudError` is raised with an actionable message.

### 2.2 Query Method

```python
result = client.observability.query(
    prompt_id: str,                         # Required -- prompt identifier
    from_date: datetime,                    # Required -- start of time range
    *,
    version: str | None = None,             # Filter by prompt version
    to_date: datetime | None = None,        # End of time range
    trace_id: str | None = None,            # Filter to specific trace
    span_names: list[str] | None = None,    # Filter by span name (max 20)
    depth: int = 0,                         # Child span depth (-1 to 10; 0 = root only)
    select_attributes: list[str] | None = None,  # Specific attributes to include (max 50)
    include_all_attributes: bool = False,
    include_resource_attributes: bool = False,
    include_events: bool = False,
    include_links: bool = False,
    span_filters: list[FilterCondition] | None = None,   # max 20
    resource_filters: list[FilterCondition] | None = None, # max 20
    order_by: list[OrderBySpec] | None = None,
    page: int = 1,                          # 1-based page number
    limit: int = 10,                        # Results per page (0 = unlimited)
) -> TelemetryQueryResponse
```

### 2.3 Server Contract

- **Endpoint:** `POST <app_url>/prompts/telemetry/query`
- **Auth:** `Authorization: Bearer <api_key>` (via `get_api_key_context` dependency)
- **Server-injected:** `project_id` extracted from API key context (not sent by client)
- **Source schema:** `services/budapp/budapp/prompt_ops/schemas.py` lines 1029-1114

### 2.4 Response Models

**Success (200):**
```json
{
  "object": "telemetry_query",
  "data": [{ "timestamp": "...", "trace_id": "...", "span_id": "...", ... }],
  "page": 1,
  "limit": 10,
  "total_record": 42,
  "has_more": true,
  "code": 200,
  "message": null
}
```

**Error (4xx/5xx):**
```json
{
  "object": "error",
  "code": 500,
  "message": "Failed to query telemetry",
  "type": "InternalServerErrorerror",
  "param": null
}
```

Error responses are automatically mapped by `HttpClient._handle_response()`:
- `401` -> `AuthenticationError`
- `404` -> `NotFoundError`
- `422` -> `ValidationError`
- `429` -> `RateLimitError`
- `500+` -> `BudError`

### 2.5 Filter Operators

`eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in_`, `not_in`, `like`, `is_null`, `is_not_null`

## 3. Architecture

- **Dual HTTP client:** Lazy second `HttpClient`/`AsyncHttpClient` created on first `client.observability` access
- **Shared auth:** Same `AuthProvider` instance (token refresh benefits both clients)
- **Isolation:** App service downtime cannot affect gateway inference operations
- **Connection pools:** Independent per-host httpx pools, no contention

## 4. Files

| File | Action |
|------|--------|
| `src/bud/models/telemetry.py` | CREATE |
| `src/bud/resources/observability.py` | CREATE |
| `src/bud/client.py` | MODIFY |
| `src/bud/_config.py` | MODIFY |
| `src/bud/__init__.py` | MODIFY |
| `tests/unit/test_telemetry/` | CREATE |
| `examples/observability/query_telemetry.py` | CREATE |

## 5. Constraints

- Python 3.11+, pydantic v2, httpx
- No new dependencies required
- `project_id` is NEVER sent by the SDK (server extracts it from API key)
- `page` is 1-based (ge=1), not offset-based
- Both sync and async variants required
