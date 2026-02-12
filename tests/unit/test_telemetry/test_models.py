"""Tests for telemetry Pydantic models."""

from __future__ import annotations

from bud.models.telemetry import (
    FilterCondition,
    FilterOperator,
    OrderBySpec,
    TelemetryErrorResponse,
    TelemetryQueryResponse,
    TelemetrySpanItem,
)


def test_telemetry_query_response_basic() -> None:
    """Test basic TelemetryQueryResponse parsing."""
    data = {
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
    resp = TelemetryQueryResponse.model_validate(data)

    assert resp.object == "telemetry_query"
    assert len(resp.data) == 1
    assert resp.data[0].trace_id == "abc123"
    assert resp.data[0].span_name == "chat_completions"
    assert resp.data[0].duration == 150
    assert resp.page == 1
    assert resp.total_record == 1
    assert resp.total_pages == 1


def test_telemetry_query_response_defaults() -> None:
    """Test TelemetryQueryResponse with minimal data."""
    resp = TelemetryQueryResponse.model_validate({})

    assert resp.data == []
    assert resp.page == 1
    assert resp.limit == 10
    assert resp.total_record == 0
    assert resp.total_pages == 1


def test_telemetry_span_item_recursive_children() -> None:
    """Test TelemetrySpanItem with nested children."""
    data = {
        "timestamp": "2025-01-15T10:00:00Z",
        "trace_id": "abc123",
        "span_id": "parent-1",
        "span_name": "root",
        "child_count": 2,
        "children": [
            {
                "timestamp": "2025-01-15T10:00:01Z",
                "trace_id": "abc123",
                "span_id": "child-1",
                "span_name": "child_span",
                "children": [
                    {
                        "timestamp": "2025-01-15T10:00:02Z",
                        "trace_id": "abc123",
                        "span_id": "grandchild-1",
                        "span_name": "grandchild_span",
                    }
                ],
            },
            {
                "timestamp": "2025-01-15T10:00:01Z",
                "trace_id": "abc123",
                "span_id": "child-2",
                "span_name": "child_span_2",
            },
        ],
    }
    span = TelemetrySpanItem.model_validate(data)

    assert span.span_id == "parent-1"
    assert len(span.children) == 2
    assert span.children[0].span_id == "child-1"
    assert len(span.children[0].children) == 1
    assert span.children[0].children[0].span_id == "grandchild-1"
    assert span.children[1].span_id == "child-2"
    assert len(span.children[1].children) == 0


def test_telemetry_span_item_with_attributes() -> None:
    """Test TelemetrySpanItem with optional attribute fields."""
    data = {
        "timestamp": "2025-01-15T10:00:00Z",
        "trace_id": "abc123",
        "span_id": "span-1",
        "span_name": "chat",
        "attributes": {"gen_ai.system": "openai", "gen_ai.request.model": "gpt-4"},
        "resource_attributes": {"service.name": "my-service"},
        "events": [{"name": "exception", "timestamp": "2025-01-15T10:00:01Z"}],
        "links": [{"trace_id": "linked-trace", "span_id": "linked-span"}],
    }
    span = TelemetrySpanItem.model_validate(data)

    assert span.attributes["gen_ai.system"] == "openai"
    assert span.resource_attributes is not None
    assert span.resource_attributes["service.name"] == "my-service"
    assert span.events is not None
    assert len(span.events) == 1
    assert span.links is not None
    assert len(span.links) == 1


def test_filter_condition_serialization() -> None:
    """Test FilterCondition model_dump."""
    fc = FilterCondition(field="status_code", op=FilterOperator.eq, value="ERROR")
    dumped = fc.model_dump()

    assert dumped["field"] == "status_code"
    assert dumped["op"] == "eq"
    assert dumped["value"] == "ERROR"


def test_filter_condition_null_operator() -> None:
    """Test FilterCondition with is_null operator (no value needed)."""
    fc = FilterCondition(field="error", op=FilterOperator.is_null)
    dumped = fc.model_dump()

    assert dumped["op"] == "is_null"
    assert dumped["value"] is None


def test_order_by_spec_serialization() -> None:
    """Test OrderBySpec model_dump."""
    obs = OrderBySpec(field="timestamp", direction="asc")
    dumped = obs.model_dump()

    assert dumped["field"] == "timestamp"
    assert dumped["direction"] == "asc"


def test_order_by_spec_default_direction() -> None:
    """Test OrderBySpec defaults to desc."""
    obs = OrderBySpec(field="duration")
    assert obs.direction == "desc"


def test_telemetry_error_response() -> None:
    """Test TelemetryErrorResponse parsing."""
    data = {
        "object": "error",
        "code": 500,
        "message": "Failed to query telemetry",
        "type": "InternalServerErrorerror",
        "param": None,
    }
    err = TelemetryErrorResponse.model_validate(data)

    assert err.object == "error"
    assert err.code == 500
    assert err.message == "Failed to query telemetry"


def test_filter_operator_values() -> None:
    """Test all FilterOperator enum values."""
    expected = {
        "eq",
        "neq",
        "gt",
        "gte",
        "lt",
        "lte",
        "in_",
        "not_in",
        "like",
        "is_null",
        "is_not_null",
    }
    actual = {op.value for op in FilterOperator}
    assert actual == expected
