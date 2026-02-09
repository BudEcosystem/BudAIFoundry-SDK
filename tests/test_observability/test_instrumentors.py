"""Tests for _instrumentors.py — Registry with missing/present deps."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from bud.observability._instrumentors import InstrumentorRegistry


class TestInstrumentorRegistry:
    def test_unknown_instrumentor_skipped(self) -> None:
        result = InstrumentorRegistry.register_all(["nonexistent"], MagicMock())
        assert result == []

    def test_missing_dep_skipped(self) -> None:
        with patch(
            "bud.observability._instrumentors._instrument_httpx",
            side_effect=ImportError("missing"),
        ):
            result = InstrumentorRegistry.register_all(["httpx"], MagicMock())
        assert result == []

    def test_failed_instrumentor_continues(self) -> None:
        with patch(
            "bud.observability._instrumentors._instrument_httpx",
            side_effect=RuntimeError("oops"),
        ):
            result = InstrumentorRegistry.register_all(["httpx"], MagicMock())
        assert result == []

    def test_successful_instrumentor(self) -> None:
        mock_handler = MagicMock()
        with patch.dict(InstrumentorRegistry._REGISTRY, {"test_inst": mock_handler}):
            result = InstrumentorRegistry.register_all(["test_inst"], MagicMock())
        assert result == ["test_inst"]
        mock_handler.assert_called_once()

    def test_multiple_instrumentors(self) -> None:
        mock_a = MagicMock()
        mock_b = MagicMock()
        with patch.dict(
            InstrumentorRegistry._REGISTRY,
            {"inst_a": mock_a, "inst_b": mock_b},
            clear=False,
        ):
            result = InstrumentorRegistry.register_all(["inst_a", "inst_b"], MagicMock())
        assert "inst_a" in result
        assert "inst_b" in result
