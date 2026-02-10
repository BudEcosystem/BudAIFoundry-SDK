"""Tests for _state.py — Thread-safe singleton lifecycle."""

from __future__ import annotations

from bud.observability._config import ObservabilityConfig, ObservabilityMode
from bud.observability._state import _ObservabilityState


class TestObservabilityState:
    def _make_state(self) -> _ObservabilityState:
        return _ObservabilityState()

    def test_not_configured_initially(self) -> None:
        state = self._make_state()
        assert state.is_configured is False

    def test_configure_disabled(self) -> None:
        state = self._make_state()
        config = ObservabilityConfig(mode=ObservabilityMode.DISABLED)
        state.configure(config)
        assert state.is_configured is True
        state.shutdown()

    def test_configure_not_enabled(self) -> None:
        state = self._make_state()
        config = ObservabilityConfig(enabled=False)
        state.configure(config)
        assert state.is_configured is True
        state.shutdown()

    def test_configure_idempotent(self) -> None:
        state = self._make_state()
        config = ObservabilityConfig(mode=ObservabilityMode.DISABLED)
        state.configure(config)
        # Second call should warn and no-op
        state.configure(config)
        assert state.is_configured is True
        state.shutdown()

    def test_get_tracer_noop_before_configure(self) -> None:
        state = self._make_state()
        tracer = state.get_tracer("test")
        from bud.observability._noop import _NoOpTracer

        assert isinstance(tracer, _NoOpTracer)

    def test_get_meter_noop_before_configure(self) -> None:
        state = self._make_state()
        meter = state.get_meter("test")
        from bud.observability._noop import _NoOpMeter

        assert isinstance(meter, _NoOpMeter)

    def test_shutdown_clears_state(self) -> None:
        state = self._make_state()
        config = ObservabilityConfig(mode=ObservabilityMode.DISABLED)
        state.configure(config)
        assert state.is_configured is True
        state.shutdown()
        assert state.is_configured is False

    def test_configure_create_mode(self) -> None:
        state = self._make_state()
        config = ObservabilityConfig(
            mode=ObservabilityMode.CREATE,
            collector_endpoint="http://localhost:4318",
            compression="none",
            traces_enabled=True,
            metrics_enabled=False,
            logs_enabled=False,
        )
        state.configure(config)
        assert state.is_configured is True
        tracer = state.get_tracer("test")
        # Should be a real tracer, not NoOp
        from bud.observability._noop import _NoOpTracer

        assert not isinstance(tracer, _NoOpTracer)
        state.shutdown()

    def test_shutdown_without_configure_is_safe(self) -> None:
        state = self._make_state()
        state.shutdown()  # Should not raise
