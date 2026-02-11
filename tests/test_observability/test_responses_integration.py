"""Integration tests for track_responses() — full span lifecycle."""

from __future__ import annotations

import json
from unittest.mock import Mock, patch

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from bud.observability._genai_attributes import (
    BUD_INFERENCE_CHUNKS,
    BUD_INFERENCE_OPERATION,
    BUD_INFERENCE_STREAM,
    BUD_INFERENCE_STREAM_COMPLETED,
    BUD_INFERENCE_TTFT_MS,
    GENAI_OPERATION_NAME,
    GENAI_OUTPUT_MESSAGES,
    GENAI_RESPONSE_ID,
    GENAI_RESPONSE_MODEL,
    GENAI_RESPONSE_OBJECT,
    GENAI_RESPONSE_STATUS,
    GENAI_SYSTEM,
    GENAI_SYSTEM_INSTRUCTIONS,
    GENAI_USAGE,
    GENAI_USAGE_INPUT_TOKENS,
    GENAI_USAGE_OUTPUT_TOKENS,
    GENAI_USAGE_TOTAL_TOKENS,
)
from bud.observability._responses_tracker import track_responses

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def traced_env():
    """Set up a traced environment with InMemorySpanExporter."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    def _get_tracer(name="bud"):
        return provider.get_tracer(name)

    with (
        patch("bud.observability._track._is_noop", return_value=False),
        patch("bud.observability.get_tracer", side_effect=_get_tracer),
        patch("bud.observability._responses_tracker._is_noop", return_value=False),
    ):
        yield exporter, provider

    provider.shutdown()


def _make_client(create_return_value=None):
    """Create a mock BudClient with responses.create()."""
    client = Mock()
    client.responses = Mock()
    client.responses.create = Mock(return_value=create_return_value)
    client.responses._bud_tracked = False
    return client


def _make_response():
    """Create a realistic mock openai.types.responses.Response."""
    usage = Mock()
    usage.input_tokens = 10
    usage.output_tokens = 5
    usage.total_tokens = 15
    usage.model_dump = Mock(return_value={
        "input_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15,
    })

    output_item = Mock()
    output_item.model_dump = Mock(return_value={
        "type": "message",
        "role": "assistant",
        "content": [{"type": "output_text", "text": "Hello!"}],
    })

    response = Mock()
    response.id = "resp_test"
    response.model = "gpt-4.1"
    response.status = "completed"
    response.created_at = 1700000000.0
    response.usage = usage
    response.object = "response"
    response.output = [output_item]
    response.instructions = "You are helpful"
    response.background = None
    response.parallel_tool_calls = None
    response.max_output_tokens = None
    response.temperature = 1.0
    response.top_p = 1.0
    response.service_tier = None
    response.tools = None
    response.tool_choice = None
    response.reasoning = None
    response.text = None
    response.prompt = None
    return response


def _make_stream_events(texts, with_completed=True):
    """Create a list of mock stream events with an optional response.completed event."""
    events = []
    for text in texts:
        event = Mock()
        event.type = "response.output_text.delta"
        event.delta = text
        events.append(event)

    if with_completed:
        completed_event = Mock()
        completed_event.type = "response.completed"
        completed_event.response = _make_response()
        events.append(completed_event)

    return events


def _make_mock_stream(events):
    """Create a mock ResponseStream that yields events and has completed_response."""
    stream = Mock()
    stream.__iter__ = Mock(return_value=iter(events))

    # Find the completed response from events
    completed = None
    for e in events:
        if getattr(e, "type", None) == "response.completed":
            completed = e.response
            break
    stream.completed_response = completed
    return stream


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNonStreamingSpan:
    def test_span_created_with_correct_attributes(self, traced_env):  # noqa: ARG002
        exporter, _provider = traced_env
        response = _make_response()
        client = _make_client(create_return_value=response)
        track_responses(client)

        result = client.responses.create(model="gpt-4.1", input="Hello")

        assert result is response
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "responses"
        attrs = dict(span.attributes)
        assert attrs[GENAI_SYSTEM] == "bud"
        assert attrs[BUD_INFERENCE_OPERATION] == "responses"
        assert attrs[GENAI_OPERATION_NAME] == "responses"
        assert attrs[BUD_INFERENCE_STREAM] is False
        assert attrs["gen_ai.request.model"] == "gpt-4.1"
        assert attrs[GENAI_RESPONSE_ID] == "resp_test"
        assert attrs[GENAI_RESPONSE_MODEL] == "gpt-4.1"
        assert attrs[GENAI_RESPONSE_STATUS] == "completed"
        assert attrs[GENAI_USAGE_INPUT_TOKENS] == 10
        assert attrs[GENAI_USAGE_OUTPUT_TOKENS] == 5
        assert attrs[GENAI_USAGE_TOTAL_TOKENS] == 15
        assert attrs[GENAI_RESPONSE_OBJECT] == "response"
        # Output array captured as JSON
        output_parsed = json.loads(attrs[GENAI_OUTPUT_MESSAGES])
        assert isinstance(output_parsed, list)
        assert output_parsed[0]["type"] == "message"
        # Instructions captured as-is (string, not JSON-wrapped)
        assert attrs[GENAI_SYSTEM_INSTRUCTIONS] == "You are helpful"
        # Usage full JSON
        usage_parsed = json.loads(attrs[GENAI_USAGE])
        assert usage_parsed["input_tokens"] == 10
        assert span.status.status_code == StatusCode.OK


class TestStreamingSpan:
    def test_streaming_span_attributes(self, traced_env):  # noqa: ARG002
        exporter, _provider = traced_env
        events = _make_stream_events(["Hello", " ", "world"])
        stream = _make_mock_stream(events)
        client = _make_client(create_return_value=stream)
        track_responses(client)

        result_stream = client.responses.create(model="gpt-4.1", input="Hello", stream=True)

        collected = list(result_stream)
        # 3 text deltas + 1 response.completed
        assert len(collected) == 4

        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "responses.stream"
        attrs = dict(span.attributes)
        assert attrs[GENAI_SYSTEM] == "bud"
        assert attrs[BUD_INFERENCE_STREAM] is True
        assert attrs[BUD_INFERENCE_CHUNKS] == 4
        assert attrs[BUD_INFERENCE_STREAM_COMPLETED] is True
        assert BUD_INFERENCE_TTFT_MS in attrs
        assert attrs[BUD_INFERENCE_TTFT_MS] >= 0
        # Usage from completed_response
        assert attrs[GENAI_USAGE_INPUT_TOKENS] == 10
        assert attrs[GENAI_USAGE_OUTPUT_TOKENS] == 5
        # Output messages from completed_response
        output_parsed = json.loads(attrs[GENAI_OUTPUT_MESSAGES])
        assert isinstance(output_parsed, list)
        assert span.status.status_code == StatusCode.OK

    def test_completed_response_proxied(self, traced_env):  # noqa: ARG002
        _exporter, _provider = traced_env
        events = _make_stream_events(["Hello"])
        stream = _make_mock_stream(events)
        client = _make_client(create_return_value=stream)
        track_responses(client)

        result_stream = client.responses.create(model="gpt-4.1", input="Hi", stream=True)
        list(result_stream)  # consume the stream

        # TracedResponseStream must proxy completed_response from inner stream
        assert result_stream.completed_response is not None
        assert result_stream.completed_response.id == "resp_test"

    def test_partial_streaming(self, traced_env):  # noqa: ARG002
        exporter, _provider = traced_env
        events = _make_stream_events(["a", "b", "c", "d"])
        stream = _make_mock_stream(events)
        client = _make_client(create_return_value=stream)
        track_responses(client)

        result_stream = client.responses.create(model="gpt-4.1", input="", stream=True)

        collected = []
        for event in result_stream:
            collected.append(event)
            if len(collected) == 2:
                break

        assert len(collected) == 2

        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        attrs = dict(span.attributes)
        assert attrs[BUD_INFERENCE_CHUNKS] == 2
        assert attrs[BUD_INFERENCE_STREAM_COMPLETED] is False
        assert span.status.status_code != StatusCode.ERROR


class TestErrorSpan:
    def test_error_recorded_and_reraised(self, traced_env):  # noqa: ARG002
        exporter, _provider = traced_env
        client = _make_client()
        client.responses.create.side_effect = RuntimeError("API error")
        track_responses(client)

        with pytest.raises(RuntimeError, match="API error"):
            client.responses.create(model="gpt-4.1", input="Hello")

        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.status.status_code == StatusCode.ERROR
        assert any(e.name == "exception" for e in span.events)


class TestFieldListMode:
    def test_capture_only_model(self, traced_env):  # noqa: ARG002
        exporter, _provider = traced_env
        response = _make_response()
        client = _make_client(create_return_value=response)
        track_responses(client, capture_input=["model"])

        client.responses.create(model="gpt-4.1", temperature=0.5, input="Hello")

        spans = exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs["gen_ai.request.model"] == "gpt-4.1"
        assert "gen_ai.request.temperature" not in attrs


class TestCaptureFalse:
    def test_no_input_output_attributes(self, traced_env):  # noqa: ARG002
        exporter, _provider = traced_env
        response = _make_response()
        client = _make_client(create_return_value=response)
        track_responses(client, capture_input=False, capture_output=False)

        client.responses.create(model="gpt-4.1", input="Hello")

        spans = exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        # Always-on attributes should be present
        assert attrs[GENAI_SYSTEM] == "bud"
        assert attrs[BUD_INFERENCE_OPERATION] == "responses"
        # Request/response attributes should NOT be present
        assert "gen_ai.request.model" not in attrs
        assert GENAI_RESPONSE_ID not in attrs
        assert GENAI_USAGE_INPUT_TOKENS not in attrs


class TestTrackNesting:
    def test_parent_child_with_track_decorator(self, traced_env):  # noqa: ARG002
        exporter, _provider = traced_env
        response = _make_response()
        client = _make_client(create_return_value=response)
        track_responses(client)

        from bud.observability._track import track

        @track(name="pipeline")
        def pipeline():
            return client.responses.create(model="gpt-4.1", input="Hello")

        pipeline()

        spans = exporter.get_finished_spans()
        assert len(spans) == 2

        resp_span = next(s for s in spans if s.name == "responses")
        pipeline_span = next(s for s in spans if s.name == "pipeline")

        assert resp_span.parent is not None
        assert resp_span.parent.span_id == pipeline_span.context.span_id
