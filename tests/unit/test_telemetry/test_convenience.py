"""Tests for the convenience helpers in the observability module."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from bud.models.telemetry import FilterCondition, FilterOperator, OrderBySpec
from bud.resources.observability import (
    _normalize_filters,
    _normalize_order_by,
    _resolve_date,
)

# ── _resolve_date ────────────────────────────────────────────────────────────


class TestResolveDate:
    def test_none_returns_none(self) -> None:
        assert _resolve_date(None) is None

    def test_date_only_string(self) -> None:
        result = _resolve_date("2026-02-05")
        assert result == datetime(2026, 2, 5, tzinfo=timezone.utc)

    def test_datetime_string_with_z(self) -> None:
        result = _resolve_date("2026-02-05T13:07:00Z")
        assert result == datetime(2026, 2, 5, 13, 7, 0, tzinfo=timezone.utc)

    def test_datetime_string_with_offset(self) -> None:
        result = _resolve_date("2026-02-05T13:07:00+00:00")
        assert result == datetime(2026, 2, 5, 13, 7, 0, tzinfo=timezone.utc)

    def test_aware_datetime_passthrough(self) -> None:
        dt = datetime(2026, 2, 5, tzinfo=timezone.utc)
        assert _resolve_date(dt) is dt

    def test_naive_datetime_gets_utc(self) -> None:
        dt = datetime(2026, 2, 5)
        result = _resolve_date(dt)
        assert result is not dt
        assert result == datetime(2026, 2, 5, tzinfo=timezone.utc)
        assert result.tzinfo is timezone.utc

    def test_invalid_string_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            _resolve_date("not-a-date")

    def test_wrong_type_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="Expected str or datetime, got int"):
            _resolve_date(12345)  # type: ignore[arg-type]


# ── _normalize_filters ───────────────────────────────────────────────────────


class TestNormalizeFilters:
    def test_none_returns_none(self) -> None:
        assert _normalize_filters(None) is None

    def test_list_of_dicts(self) -> None:
        result = _normalize_filters(
            [
                {"field": "status_code", "op": "eq", "value": "200"},
            ]
        )
        assert result is not None
        assert len(result) == 1
        assert isinstance(result[0], FilterCondition)
        assert result[0].field == "status_code"
        assert result[0].op is FilterOperator.eq
        assert result[0].value == "200"

    def test_list_of_filter_conditions(self) -> None:
        fc = FilterCondition(field="x", op=FilterOperator.gt, value="5")
        result = _normalize_filters([fc])
        assert result is not None
        assert result[0] is fc

    def test_mixed_list(self) -> None:
        fc = FilterCondition(field="a", op=FilterOperator.eq, value="1")
        result = _normalize_filters(
            [
                fc,
                {"field": "b", "op": "neq", "value": "2"},
            ]
        )
        assert result is not None
        assert len(result) == 2
        assert result[0] is fc
        assert isinstance(result[1], FilterCondition)
        assert result[1].op is FilterOperator.neq


# ── _normalize_order_by ──────────────────────────────────────────────────────


class TestNormalizeOrderBy:
    def test_none_returns_none(self) -> None:
        assert _normalize_order_by(None) is None

    def test_list_of_dicts(self) -> None:
        result = _normalize_order_by(
            [
                {"field": "timestamp", "direction": "asc"},
            ]
        )
        assert result is not None
        assert len(result) == 1
        assert isinstance(result[0], OrderBySpec)
        assert result[0].field == "timestamp"
        assert result[0].direction == "asc"

    def test_list_of_order_by_specs(self) -> None:
        ob = OrderBySpec(field="duration", direction="desc")
        result = _normalize_order_by([ob])
        assert result is not None
        assert result[0] is ob

    def test_mixed_list(self) -> None:
        ob = OrderBySpec(field="a", direction="asc")
        result = _normalize_order_by(
            [
                ob,
                {"field": "b", "direction": "desc"},
            ]
        )
        assert result is not None
        assert len(result) == 2
        assert result[0] is ob
        assert isinstance(result[1], OrderBySpec)

    def test_dict_default_direction(self) -> None:
        result = _normalize_order_by([{"field": "timestamp"}])
        assert result is not None
        assert result[0].direction == "desc"
