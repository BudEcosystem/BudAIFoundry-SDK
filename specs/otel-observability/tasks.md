# Tasks: SDK Observability Query API

## Implementation Tasks

- [x] **1. Create Pydantic models** -- `src/bud/models/telemetry.py`
  - FilterOperator enum, FilterCondition, OrderBySpec, TelemetrySpanItem, TelemetryQueryResponse, TelemetryErrorResponse
  - Mirror budapp schemas from `services/budapp/budapp/prompt_ops/schemas.py` lines 1029-1114
  - Use page-based pagination (page: int = 1, limit: int = 10)

- [x] **2. Create Observability resource** -- `src/bud/resources/observability.py`
  - Sync `Observability(SyncResource)` with `query()` method
  - Async `AsyncObservability(AsyncResource)` with `query()` method
  - POST to `/prompts/telemetry/query`, validate response with `TelemetryQueryResponse.model_validate()`
  - Follow existing resource pattern from `src/bud/resources/_base.py`

- [x] **3. Add app_url to config** -- `src/bud/_config.py`
  - Add `app_url: str | None = None` field to `BudConfig`
  - Support `BUD_APP_URL` env var in `from_env()`
  - Support `app_url` key in `from_file()`
  - Override in `load()` if env var is set

- [x] **4. Add dual HTTP client to BudClient** -- `src/bud/client.py`
  - Add `app_url` and `app_timeout` keyword params to `BudClient.__init__`
  - Add lazy `_app_http` property (creates `HttpClient` on first access)
  - Add lazy `observability` property (creates `Observability` resource)
  - Raise `BudError` if `app_url` not configured when accessed
  - Update `close()` to also close `__app_http` if created
  - Same changes for `AsyncBudClient` (using `AsyncHttpClient` + `AsyncObservability`)

- [x] **5. Export new models** -- `src/bud/__init__.py`
  - Export FilterCondition, FilterOperator, OrderBySpec, TelemetryErrorResponse, TelemetryQueryResponse, TelemetrySpanItem

- [x] **6. Write unit tests** -- `tests/unit/test_telemetry/`
  - `test_models.py`: model validation, recursive children, serialization
  - `test_resource.py`: basic query, all params, typed response, auth header, error 401/404/422/500, app_url not configured, lazy init, close cleanup
  - `test_async_resource.py`: async variants of all sync tests
  - Use `respx` for HTTP mocking (existing SDK test pattern)

- [x] **7. Write usage example** -- `examples/observability/query_telemetry.py`
  - Basic query, filtered query, pagination loop, trace lookup
  - Import from `bud` package (FilterCondition, FilterOperator, OrderBySpec)

## Verification Tasks

- [x] **8. Run linting** -- `uv run ruff check src/ tests/`
- [x] **9. Run type checking** -- `uv run mypy src/bud --ignore-missing-imports`
- [x] **10. Run all tests** -- `uv run pytest tests/ -v` (existing + new must pass)
