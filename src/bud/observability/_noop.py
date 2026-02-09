"""No-op implementations for when OpenTelemetry dependencies are not installed.

All methods are completely safe and never raise exceptions.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from typing import Any


def _check_otel_available() -> bool:
    """Test whether OpenTelemetry SDK packages are importable."""
    try:
        import opentelemetry.sdk.trace  # noqa: F401

        return True
    except ImportError:
        return False


class _NoOpSpan:
    """A span that does nothing. Implements the OTel Span interface as no-ops."""

    def end(self, end_time: Any = None) -> None:  # noqa: ARG002
        pass

    def get_span_context(self) -> Any:
        return None

    def set_attribute(self, key: str, value: Any) -> None:  # noqa: ARG002
        pass

    def set_attributes(self, attributes: Any) -> None:  # noqa: ARG002
        pass

    def add_event(  # noqa: ARG002
        self, name: str, attributes: Any = None, timestamp: Any = None
    ) -> None:
        pass

    def set_status(self, status: Any, description: str | None = None) -> None:  # noqa: ARG002
        pass

    def record_exception(  # noqa: ARG002
        self,
        exception: BaseException,
        attributes: Any = None,
        timestamp: Any = None,
        escaped: bool = False,
    ) -> None:
        pass

    def update_name(self, name: str) -> None:  # noqa: ARG002
        pass

    def is_recording(self) -> bool:
        return False

    def __enter__(self) -> _NoOpSpan:
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class _NoOpTracer:
    """A tracer that returns no-op spans."""

    def start_span(self, name: str, **kwargs: Any) -> _NoOpSpan:  # noqa: ARG002
        return _NoOpSpan()

    @contextlib.contextmanager
    def start_as_current_span(self, name: str, **kwargs: Any) -> Iterator[_NoOpSpan]:  # noqa: ARG002
        yield _NoOpSpan()


class _NoOpCounter:
    """A counter instrument that does nothing."""

    def add(self, amount: int | float, attributes: Any = None) -> None:  # noqa: ARG002
        pass


class _NoOpHistogram:
    """A histogram instrument that does nothing."""

    def record(self, amount: int | float, attributes: Any = None) -> None:  # noqa: ARG002
        pass


class _NoOpUpDownCounter:
    """An up-down counter instrument that does nothing."""

    def add(self, amount: int | float, attributes: Any = None) -> None:  # noqa: ARG002
        pass


class _NoOpMeter:
    """A meter that returns no-op instruments."""

    def create_counter(self, name: str, **kwargs: Any) -> _NoOpCounter:  # noqa: ARG002
        return _NoOpCounter()

    def create_histogram(self, name: str, **kwargs: Any) -> _NoOpHistogram:  # noqa: ARG002
        return _NoOpHistogram()

    def create_up_down_counter(self, name: str, **kwargs: Any) -> _NoOpUpDownCounter:  # noqa: ARG002
        return _NoOpUpDownCounter()

    def create_observable_counter(self, name: str, **kwargs: Any) -> _NoOpCounter:  # noqa: ARG002
        return _NoOpCounter()

    def create_observable_up_down_counter(self, name: str, **kwargs: Any) -> _NoOpUpDownCounter:  # noqa: ARG002
        return _NoOpUpDownCounter()
