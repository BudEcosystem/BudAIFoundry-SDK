"""Tests for _instrumentors.py — Explicit instrument_fastapi / instrument_httpx."""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch

import pytest

from bud.observability._instrumentors import instrument_fastapi, instrument_httpx


def _fake_fastapi_module(mock_cls: MagicMock) -> types.ModuleType:
    """Create a fake opentelemetry.instrumentation.fastapi module."""
    mod = types.ModuleType("opentelemetry.instrumentation.fastapi")
    mod.FastAPIInstrumentor = mock_cls  # type: ignore[attr-defined]
    return mod


def _fake_httpx_module(mock_cls: MagicMock) -> types.ModuleType:
    """Create a fake opentelemetry.instrumentation.httpx module."""
    mod = types.ModuleType("opentelemetry.instrumentation.httpx")
    mod.HTTPXClientInstrumentor = mock_cls  # type: ignore[attr-defined]
    return mod


class TestInstrumentFastapi:
    def test_instruments_app_with_tracer_provider(self) -> None:
        mock_instrumentor_cls = MagicMock()
        mock_tp = MagicMock()
        fake_mod = _fake_fastapi_module(mock_instrumentor_cls)

        # Patch the _state singleton's _tracer_provider
        with (
            patch.dict(sys.modules, {"opentelemetry.instrumentation.fastapi": fake_mod}),
            patch("bud.observability._state._state._tracer_provider", mock_tp),
        ):
            app = MagicMock()
            instrument_fastapi(app)

        mock_instrumentor_cls.instrument_app.assert_called_once_with(
            app,
            tracer_provider=mock_tp,
        )

    def test_generic_exception_does_not_raise(self) -> None:
        mock_instrumentor_cls = MagicMock()
        mock_instrumentor_cls.instrument_app.side_effect = RuntimeError("boom")
        fake_mod = _fake_fastapi_module(mock_instrumentor_cls)

        with patch.dict(sys.modules, {"opentelemetry.instrumentation.fastapi": fake_mod}):
            # Should not raise
            instrument_fastapi(MagicMock())

    def test_missing_dep_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """ImportError is caught and logged as a warning."""
        import logging

        with (
            patch.dict(sys.modules, {"opentelemetry.instrumentation.fastapi": None}),
            caplog.at_level(logging.WARNING, logger="bud.observability"),
        ):
            instrument_fastapi(MagicMock())
        assert "FastAPI instrumentation not installed" in caplog.text


class TestInstrumentHttpx:
    def test_global_instrumentation(self) -> None:
        mock_instrumentor = MagicMock()
        mock_instrumentor_cls = MagicMock(return_value=mock_instrumentor)
        mock_tp = MagicMock()
        fake_mod = _fake_httpx_module(mock_instrumentor_cls)

        with (
            patch.dict(sys.modules, {"opentelemetry.instrumentation.httpx": fake_mod}),
            patch("bud.observability._state._state._tracer_provider", mock_tp),
        ):
            instrument_httpx()

        mock_instrumentor.instrument.assert_called_once_with(
            tracer_provider=mock_tp,
        )

    def test_per_client_instrumentation(self) -> None:
        mock_instrumentor = MagicMock()
        mock_instrumentor_cls = MagicMock(return_value=mock_instrumentor)
        mock_tp = MagicMock()
        fake_mod = _fake_httpx_module(mock_instrumentor_cls)

        with (
            patch.dict(sys.modules, {"opentelemetry.instrumentation.httpx": fake_mod}),
            patch("bud.observability._state._state._tracer_provider", mock_tp),
        ):
            client = MagicMock()
            instrument_httpx(client)

        mock_instrumentor.instrument_client.assert_called_once_with(
            client,
            tracer_provider=mock_tp,
        )

    def test_missing_dep_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """ImportError is caught and logged as a warning."""
        import logging

        with (
            patch.dict(sys.modules, {"opentelemetry.instrumentation.httpx": None}),
            caplog.at_level(logging.WARNING, logger="bud.observability"),
        ):
            instrument_httpx()
        assert "HTTPX instrumentation not installed" in caplog.text

    def test_generic_exception_does_not_raise(self) -> None:
        mock_instrumentor = MagicMock()
        mock_instrumentor.instrument.side_effect = RuntimeError("boom")
        mock_instrumentor_cls = MagicMock(return_value=mock_instrumentor)
        fake_mod = _fake_httpx_module(mock_instrumentor_cls)

        with patch.dict(sys.modules, {"opentelemetry.instrumentation.httpx": fake_mod}):
            # Should not raise
            instrument_httpx()
