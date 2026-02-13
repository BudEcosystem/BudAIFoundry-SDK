"""Tests for the sync Observability resource."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
import respx
from httpx import Response

from bud.client import BudClient
from bud.exceptions import AuthenticationError, BudError, NotFoundError, ValidationError
from bud.models.telemetry import (
    FilterCondition,
    FilterOperator,
    OrderBySpec,
    TelemetryQueryResponse,
)

APP_URL = "https://app.test.bud.io"


def _make_client(
    api_key: str = "test-api-key-12345",
    base_url: str = "https://api.test.bud.io",
    app_url: str = APP_URL,
) -> BudClient:
    """Create a BudClient with app_url configured."""
    return BudClient(api_key=api_key, base_url=base_url, app_url=app_url)


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


@respx.mock
def test_query_basic() -> None:
    """Test basic query with minimal params."""
    route = respx.post(f"{APP_URL}/prompts/telemetry/query").mock(
        return_value=Response(200, json=SAMPLE_RESPONSE)
    )

    client = _make_client()
    client.observability.query(
        prompt_id="my-prompt",
        from_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    client.close()

    assert route.called
    request = route.calls[0].request
    import json

    body = json.loads(request.content)
    assert body["prompt_id"] == "my-prompt"
    assert body["from_date"] == "2025-01-01T00:00:00+00:00"
    # Only required fields should be in payload
    assert "version" not in body
    assert "trace_id" not in body


@respx.mock
def test_query_all_params() -> None:
    """Test query with all optional params."""
    route = respx.post(f"{APP_URL}/prompts/telemetry/query").mock(
        return_value=Response(200, json=SAMPLE_RESPONSE)
    )

    client = _make_client()
    client.observability.query(
        prompt_id="my-prompt",
        from_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        version="v2",
        to_date=datetime(2025, 6, 1, tzinfo=timezone.utc),
        trace_id="trace-xyz",
        span_names=["chat_completions", "embedding"],
        depth=3,
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
    client.close()

    import json

    body = json.loads(route.calls[0].request.content)
    assert body["prompt_id"] == "my-prompt"
    assert body["version"] == "v2"
    assert body["to_date"] == "2025-06-01T00:00:00+00:00"
    assert body["trace_id"] == "trace-xyz"
    assert body["span_names"] == ["chat_completions", "embedding"]
    assert body["depth"] == 3
    assert body["select_attributes"] == ["gen_ai.system"]
    assert body["include_all_attributes"] is True
    assert body["include_resource_attributes"] is True
    assert body["include_events"] is True
    assert body["include_links"] is True
    assert len(body["span_filters"]) == 1
    assert body["span_filters"][0]["field"] == "status_code"
    assert len(body["resource_filters"]) == 1
    assert len(body["order_by"]) == 1
    assert body["page"] == 2
    assert body["limit"] == 50


@respx.mock
def test_query_returns_typed_response() -> None:
    """Test that query returns a TelemetryQueryResponse."""
    respx.post(f"{APP_URL}/prompts/telemetry/query").mock(
        return_value=Response(200, json=SAMPLE_RESPONSE)
    )

    client = _make_client()
    result = client.observability.query(
        prompt_id="my-prompt",
        from_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    client.close()

    assert isinstance(result, TelemetryQueryResponse)
    assert result.total_record == 1
    assert len(result.data) == 1
    assert result.data[0].trace_id == "abc123"


@respx.mock
def test_query_auth_header() -> None:
    """Test that the auth header is sent correctly."""
    route = respx.post(f"{APP_URL}/prompts/telemetry/query").mock(
        return_value=Response(200, json=SAMPLE_RESPONSE)
    )

    client = _make_client(api_key="my-secret-key")
    client.observability.query(
        prompt_id="test",
        from_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    client.close()

    request = route.calls[0].request
    assert "authorization" in request.headers
    assert request.headers["authorization"] == "Bearer my-secret-key"


@respx.mock
def test_query_error_401() -> None:
    """Test that 401 raises AuthenticationError."""
    respx.post(f"{APP_URL}/prompts/telemetry/query").mock(
        return_value=Response(
            401,
            json={
                "object": "error",
                "code": 401,
                "message": "Invalid API key",
                "type": "UnauthorizedError",
            },
        )
    )

    client = _make_client()
    with pytest.raises(AuthenticationError, match="Invalid API key"):
        client.observability.query(
            prompt_id="test",
            from_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
    client.close()


@respx.mock
def test_query_error_404() -> None:
    """Test that 404 raises NotFoundError."""
    respx.post(f"{APP_URL}/prompts/telemetry/query").mock(
        return_value=Response(
            404,
            json={
                "object": "error",
                "code": 404,
                "message": "Prompt not found",
                "type": "NotFoundError",
            },
        )
    )

    client = _make_client()
    with pytest.raises(NotFoundError, match="Prompt not found"):
        client.observability.query(
            prompt_id="nonexistent",
            from_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
    client.close()


@respx.mock
def test_query_error_422() -> None:
    """Test that 422 raises ValidationError."""
    respx.post(f"{APP_URL}/prompts/telemetry/query").mock(
        return_value=Response(
            422,
            json={
                "object": "error",
                "code": 422,
                "message": "Invalid request body",
                "type": "ValidationError",
            },
        )
    )

    client = _make_client()
    with pytest.raises(ValidationError, match="Invalid request body"):
        client.observability.query(
            prompt_id="test",
            from_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
    client.close()


@respx.mock
def test_query_error_500() -> None:
    """Test that 500 raises BudError after retries."""
    respx.post(f"{APP_URL}/prompts/telemetry/query").mock(
        return_value=Response(
            500,
            json={
                "object": "error",
                "code": 500,
                "message": "Failed to query telemetry",
                "type": "InternalServerErrorerror",
            },
        )
    )

    client = _make_client()
    # HttpClient retries BudError, so after max retries we get a generic message
    with pytest.raises(BudError):
        client.observability.query(
            prompt_id="test",
            from_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
    client.close()


def test_app_url_not_configured_raises() -> None:
    """Test that accessing observability without app_url raises BudError."""
    with patch.dict("os.environ", {}, clear=False):
        # Ensure BUD_APP_URL is not set
        import os

        env = os.environ.copy()
        env.pop("BUD_APP_URL", None)
        with patch.dict("os.environ", env, clear=True):
            client = BudClient(api_key="test-key", base_url="https://api.test.bud.io")
            with pytest.raises(BudError, match="App service URL not configured"):
                _ = client.observability
            client.close()


def test_lazy_initialization() -> None:
    """Test that _app_http is not created until observability is accessed."""
    client = _make_client()

    # Before accessing observability, __app_http should be None
    assert client._BudClient__app_http is None  # type: ignore[attr-defined]
    assert client._observability is None

    client.close()


@respx.mock
def test_close_cleans_up_app_http() -> None:
    """Test that close() cleans up the app HTTP client when it was created."""
    respx.post(f"{APP_URL}/prompts/telemetry/query").mock(
        return_value=Response(200, json=SAMPLE_RESPONSE)
    )

    client = _make_client()
    # Trigger creation of app HTTP client
    client.observability.query(
        prompt_id="test",
        from_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    # App HTTP client should exist now
    assert client._BudClient__app_http is not None  # type: ignore[attr-defined]

    # Close should not raise
    client.close()


def test_close_without_observability_access() -> None:
    """Test that close() works when observability was never accessed."""
    client = _make_client()
    # No observability access, __app_http is None
    assert client._BudClient__app_http is None  # type: ignore[attr-defined]
    # close() should not raise
    client.close()


# ── Convenience API tests ─────────────────────────────────────────────────────


@respx.mock
def test_query_iso_string_date() -> None:
    """Test query with an ISO-8601 string for from_date."""
    route = respx.post(f"{APP_URL}/prompts/telemetry/query").mock(
        return_value=Response(200, json=SAMPLE_RESPONSE)
    )

    client = _make_client()
    client.observability.query(
        prompt_id="my-prompt",
        from_date="2026-02-05",
    )
    client.close()

    import json

    body = json.loads(route.calls[0].request.content)
    assert body["prompt_id"] == "my-prompt"
    assert body["from_date"] == "2026-02-05T00:00:00+00:00"


@respx.mock
def test_query_dict_filters() -> None:
    """Test query with dict-based span_filters."""
    route = respx.post(f"{APP_URL}/prompts/telemetry/query").mock(
        return_value=Response(200, json=SAMPLE_RESPONSE)
    )

    client = _make_client()
    client.observability.query(
        prompt_id="my-prompt",
        from_date="2026-02-05",
        span_filters=[
            {"field": "status_code", "op": "eq", "value": "200"},
        ],
    )
    client.close()

    import json

    body = json.loads(route.calls[0].request.content)
    assert len(body["span_filters"]) == 1
    assert body["span_filters"][0]["field"] == "status_code"
    assert body["span_filters"][0]["op"] == "eq"
    assert body["span_filters"][0]["value"] == "200"


@respx.mock
def test_query_dict_order_by() -> None:
    """Test query with dict-based order_by."""
    route = respx.post(f"{APP_URL}/prompts/telemetry/query").mock(
        return_value=Response(200, json=SAMPLE_RESPONSE)
    )

    client = _make_client()
    client.observability.query(
        prompt_id="my-prompt",
        from_date="2026-02-05",
        order_by=[{"field": "timestamp", "direction": "asc"}],
    )
    client.close()

    import json

    body = json.loads(route.calls[0].request.content)
    assert len(body["order_by"]) == 1
    assert body["order_by"][0]["field"] == "timestamp"
    assert body["order_by"][0]["direction"] == "asc"


@respx.mock
def test_query_no_from_date() -> None:
    """Test query without from_date (omitted entirely)."""
    route = respx.post(f"{APP_URL}/prompts/telemetry/query").mock(
        return_value=Response(200, json=SAMPLE_RESPONSE)
    )

    client = _make_client()
    client.observability.query(prompt_id="my-prompt")
    client.close()

    import json

    body = json.loads(route.calls[0].request.content)
    assert body["prompt_id"] == "my-prompt"
    assert "from_date" not in body
