"""Tests for ResponseStream and AsyncResponseStream."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, Mock, patch

from bud._streaming import SSEParser  # noqa: F401


class TestResponseStream:
    """Tests for sync ResponseStream."""

    def test_basic_iteration(self):
        """Test that ResponseStream yields parsed events."""
        from bud._response_streaming import ResponseStream

        sse_lines = [
            "event: response.output_text.delta",
            'data: {"type":"response.output_text.delta","item_id":"item_1","output_index":0,"content_index":0,"delta":"Hello"}',
            "",
            "event: response.output_text.delta",
            'data: {"type":"response.output_text.delta","item_id":"item_1","output_index":0,"content_index":0,"delta":" world"}',
            "",
            "data: [DONE]",
            "",
        ]

        mock_response = Mock()
        mock_response.iter_lines.return_value = iter(sse_lines)
        mock_response.close = Mock()

        with patch("bud._response_streaming._get_event_adapter") as mock_adapter:
            adapter = Mock()
            mock_adapter.return_value = adapter
            adapter.validate_python.side_effect = [
                Mock(type="response.output_text.delta", delta="Hello"),
                Mock(type="response.output_text.delta", delta=" world"),
            ]

            stream = ResponseStream(mock_response)
            events = list(stream)

            assert len(events) == 2
            assert events[0].delta == "Hello"
            assert events[1].delta == " world"

    def test_completed_response_captured(self):
        """Test that response.completed event is captured."""
        from bud._response_streaming import ResponseStream

        completed_data = {
            "type": "response.completed",
            "response": {"id": "resp_123", "status": "completed"},
        }

        sse_lines = [
            "event: response.completed",
            f"data: {json.dumps(completed_data)}",
            "",
            "data: [DONE]",
            "",
        ]

        mock_response = Mock()
        mock_response.iter_lines.return_value = iter(sse_lines)
        mock_response.close = Mock()

        mock_completed = Mock(type="response.completed")
        mock_completed.response = Mock(id="resp_123", status="completed")

        with patch("bud._response_streaming._get_event_adapter") as mock_adapter:
            adapter = Mock()
            mock_adapter.return_value = adapter
            adapter.validate_python.return_value = mock_completed

            stream = ResponseStream(mock_response)
            events = list(stream)

            assert len(events) == 1
            assert stream.completed_response is not None
            assert stream.completed_response.id == "resp_123"

    def test_done_sentinel_stops_iteration(self):
        """Test that [DONE] stops iteration."""
        from bud._response_streaming import ResponseStream

        sse_lines = [
            'data: {"type":"response.output_text.delta","delta":"Hi"}',
            "",
            "data: [DONE]",
            "",
            'data: {"type":"response.output_text.delta","delta":"ignored"}',
            "",
        ]

        mock_response = Mock()
        mock_response.iter_lines.return_value = iter(sse_lines)
        mock_response.close = Mock()

        with patch("bud._response_streaming._get_event_adapter") as mock_adapter:
            adapter = Mock()
            mock_adapter.return_value = adapter
            adapter.validate_python.return_value = Mock(type="response.output_text.delta")

            stream = ResponseStream(mock_response)
            events = list(stream)

            # Only 1 event before [DONE]
            assert len(events) == 1

    def test_json_parse_error_skipped(self):
        """Test that JSON parse errors are logged and skipped."""
        from bud._response_streaming import ResponseStream

        sse_lines = [
            "data: not-valid-json",
            "",
            'data: {"type":"response.output_text.delta","delta":"OK"}',
            "",
            "data: [DONE]",
            "",
        ]

        mock_response = Mock()
        mock_response.iter_lines.return_value = iter(sse_lines)
        mock_response.close = Mock()

        with patch("bud._response_streaming._get_event_adapter") as mock_adapter:
            adapter = Mock()
            mock_adapter.return_value = adapter
            adapter.validate_python.return_value = Mock(type="response.output_text.delta")

            stream = ResponseStream(mock_response)
            events = list(stream)

            # Only the valid event
            assert len(events) == 1

    def test_context_manager(self):
        """Test context manager closes stream."""
        from bud._response_streaming import ResponseStream

        mock_response = Mock()
        mock_response.iter_lines.return_value = iter([])
        mock_response.close = Mock()

        stream = ResponseStream(mock_response)
        with stream as s:
            assert s is stream
        mock_response.close.assert_called()

    def test_close_releases_response_context(self):
        """Test that close() exits the response context manager."""
        from bud._response_streaming import ResponseStream

        mock_response = Mock()
        mock_response.close = Mock()
        mock_ctx = MagicMock()

        stream = ResponseStream(mock_response, response_context=mock_ctx)
        stream.close()

        mock_response.close.assert_called_once()
        mock_ctx.__exit__.assert_called_once_with(None, None, None)
