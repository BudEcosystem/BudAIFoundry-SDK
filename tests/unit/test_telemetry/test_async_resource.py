"""Tests for the async Observability resource."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
import respx
from httpx import Response

from bud.client import AsyncBudClient
from bud.exceptions import AuthenticationError, BudError, NotFoundError, ValidationError
from bud.models.telemetry import (
    FilterCondition,
    FilterOperator,
    OrderBySpec,
    TelemetryQueryResponse,
)

APP_URL = "https://app.test.bud.io"


def _make_async_client(
    api_key: str = "test-api-key-12345",
    base_url: str = "https://api.test.bud.io",
    app_url: str = APP_URL,
) -> AsyncBudClient:
    """Create an AsyncBudClient with app_url configured."""
    return AsyncBudClient(api_key=api_key, base_url=base_url, app_url=app_url)


SAMPLE_RESPONSE = {
    "object": "telemetry_query",
    "data": [
        {
            "timestamp": "2025-01-15T10:00:00Z",
            "trace_id": "abc123",
            "span_id": "span-1",
            "span_name": "chat_completions",
            "duration": 150,
            "status_code": "OK",
        }
    ],
    "page": 1,
    "limit": 10,
    "total_record": 1,
    "total_pages": 1,
    "message": None,
}


@pytest.mark.anyio
@respx.mock
async def test_async_query_basic() -> None:
    """Test basic async query with minimal params."""
    route = respx.post(f"{APP_URL}/prompts/telemetry/query").mock(
        return_value=Response(200, json=SAMPLE_RESPONSE)
    )

    client = _make_async_client()
    await client.observability.query(
        prompt_id="my-prompt",
        from_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    await client.close()

    assert route.called
    import json

    body = json.loads(route.calls[0].request.content)
    assert body["prompt_id"] == "my-prompt"
    assert body["from_date"] == "2025-01-01T00:00:00+00:00"


@pytest.mark.anyio
@respx.mock
async def test_async_query_all_params() -> None:
    """Test async query with all optional params."""
    route = respx.post(f"{APP_URL}/prompts/telemetry/query").mock(
        return_value=Response(200, json=SAMPLE_RESPONSE)
    )

    client = _make_async_client()
    await client.observability.query(
        prompt_id="my-prompt",
        from_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        version="v2",
        to_date=datetime(2025, 6, 1, tzinfo=timezone.utc),
        trace_id="trace-xyz",
        span_names=["chat_completions"],
        depth=2,
        select_attributes=["gen_ai.system"],
        include_all_attributes=True,
        include_resource_attributes=True,
        include_events=True,
        include_links=True,
        span_filters=[
            FilterCondition(field="status_code", op=FilterOperator.eq, value="ERROR"),
        ],
        resource_filters=[
            FilterCondition(field="service.name", op=FilterOperator.like, value="my-%"),
        ],
        order_by=[OrderBySpec(field="timestamp", direction="desc")],
        page=2,
        limit=50,
    )
    await client.close()

    import json

    body = json.loads(route.calls[0].request.content)
    assert body["version"] == "v2"
    assert body["depth"] == 2
    assert body["page"] == 2
    assert body["limit"] == 50
    assert body["include_all_attributes"] is True


@pytest.mark.anyio
@respx.mock
async def test_async_query_returns_typed_response() -> None:
    """Test that async query returns a TelemetryQueryResponse."""
    respx.post(f"{APP_URL}/prompts/telemetry/query").mock(
        return_value=Response(200, json=SAMPLE_RESPONSE)
    )

    client = _make_async_client()
    result = await client.observability.query(
        prompt_id="my-prompt",
        from_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    await client.close()

    assert isinstance(result, TelemetryQueryResponse)
    assert result.total_record == 1


@pytest.mark.anyio
@respx.mock
async def test_async_query_auth_header() -> None:
    """Test that the auth header is sent correctly for async client."""
    route = respx.post(f"{APP_URL}/prompts/telemetry/query").mock(
        return_value=Response(200, json=SAMPLE_RESPONSE)
    )

    client = _make_async_client(api_key="my-secret-key")
    await client.observability.query(
        prompt_id="test",
        from_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    await client.close()

    request = route.calls[0].request
    assert "authorization" in request.headers
    assert request.headers["authorization"] == "Bearer my-secret-key"


@pytest.mark.anyio
@respx.mock
async def test_async_query_error_401() -> None:
    """Test that 401 raises AuthenticationError."""
    respx.post(f"{APP_URL}/prompts/telemetry/query").mock(
        return_value=Response(
            401,
            json={"object": "error", "code": 401, "message": "Invalid API key"},
        )
    )

    client = _make_async_client()
    with pytest.raises(AuthenticationError, match="Invalid API key"):
        await client.observability.query(
            prompt_id="test",
            from_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
    await client.close()


@pytest.mark.anyio
@respx.mock
async def test_async_query_error_404() -> None:
    """Test that 404 raises NotFoundError."""
    respx.post(f"{APP_URL}/prompts/telemetry/query").mock(
        return_value=Response(
            404,
            json={"object": "error", "code": 404, "message": "Prompt not found"},
        )
    )

    client = _make_async_client()
    with pytest.raises(NotFoundError, match="Prompt not found"):
        await client.observability.query(
            prompt_id="nonexistent",
            from_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
    await client.close()


@pytest.mark.anyio
@respx.mock
async def test_async_query_error_422() -> None:
    """Test that 422 raises ValidationError."""
    respx.post(f"{APP_URL}/prompts/telemetry/query").mock(
        return_value=Response(
            422,
            json={"object": "error", "code": 422, "message": "Invalid request body"},
        )
    )

    client = _make_async_client()
    with pytest.raises(ValidationError, match="Invalid request body"):
        await client.observability.query(
            prompt_id="test",
            from_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
    await client.close()


@pytest.mark.anyio
@respx.mock
async def test_async_query_error_500() -> None:
    """Test that 500 raises BudError after retries."""
    respx.post(f"{APP_URL}/prompts/telemetry/query").mock(
        return_value=Response(
            500,
            json={
                "object": "error",
                "code": 500,
                "message": "Failed to query telemetry",
            },
        )
    )

    client = _make_async_client()
    # AsyncHttpClient retries BudError, so after max retries we get a generic message
    with pytest.raises(BudError):
        await client.observability.query(
            prompt_id="test",
            from_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
    await client.close()


def test_async_app_url_not_configured_raises() -> None:
    """Test that accessing observability without app_url raises BudError."""
    import os

    env = os.environ.copy()
    env.pop("BUD_APP_URL", None)
    with patch.dict("os.environ", env, clear=True):
        client = AsyncBudClient(api_key="test-key", base_url="https://api.test.bud.io")
        with pytest.raises(BudError, match="App service URL not configured"):
            _ = client.observability
        # No close needed since we never created the app http client


def test_async_lazy_initialization() -> None:
    """Test that __app_http is not created until observability is accessed."""
    client = _make_async_client()

    assert client._AsyncBudClient__app_http is None  # type: ignore[attr-defined]
    assert client._observability is None


@pytest.mark.anyio
@respx.mock
async def test_async_close_cleans_up_app_http() -> None:
    """Test that close() cleans up app HTTP client after observability use."""
    respx.post(f"{APP_URL}/prompts/telemetry/query").mock(
        return_value=Response(200, json=SAMPLE_RESPONSE)
    )

    client = _make_async_client()
    await client.observability.query(
        prompt_id="test",
        from_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    assert client._AsyncBudClient__app_http is not None  # type: ignore[attr-defined]
    await client.close()


@pytest.mark.anyio
async def test_async_close_without_observability_access() -> None:
    """Test that close() works when observability was never accessed."""
    client = _make_async_client()
    assert client._AsyncBudClient__app_http is None  # type: ignore[attr-defined]
    await client.close()


# ── Convenience API tests ─────────────────────────────────────────────────────


@pytest.mark.anyio
@respx.mock
async def test_async_query_iso_string_date() -> None:
    """Test async query with an ISO-8601 string for from_date."""
    route = respx.post(f"{APP_URL}/prompts/telemetry/query").mock(
        return_value=Response(200, json=SAMPLE_RESPONSE)
    )

    client = _make_async_client()
    await client.observability.query(
        prompt_id="my-prompt",
        from_date="2026-02-05",
    )
    await client.close()

    import json

    body = json.loads(route.calls[0].request.content)
    assert body["from_date"] == "2026-02-05T00:00:00+00:00"


@pytest.mark.anyio
@respx.mock
async def test_async_query_dict_filters() -> None:
    """Test async query with dict-based span_filters."""
    route = respx.post(f"{APP_URL}/prompts/telemetry/query").mock(
        return_value=Response(200, json=SAMPLE_RESPONSE)
    )

    client = _make_async_client()
    await client.observability.query(
        prompt_id="my-prompt",
        from_date="2026-02-05",
        span_filters=[
            {"field": "status_code", "op": "eq", "value": "200"},
        ],
    )
    await client.close()

    import json

    body = json.loads(route.calls[0].request.content)
    assert len(body["span_filters"]) == 1
    assert body["span_filters"][0]["field"] == "status_code"


@pytest.mark.anyio
@respx.mock
async def test_async_query_dict_order_by() -> None:
    """Test async query with dict-based order_by."""
    route = respx.post(f"{APP_URL}/prompts/telemetry/query").mock(
        return_value=Response(200, json=SAMPLE_RESPONSE)
    )

    client = _make_async_client()
    await client.observability.query(
        prompt_id="my-prompt",
        from_date="2026-02-05",
        order_by=[{"field": "timestamp", "direction": "asc"}],
    )
    await client.close()

    import json

    body = json.loads(route.calls[0].request.content)
    assert len(body["order_by"]) == 1
    assert body["order_by"][0]["direction"] == "asc"
