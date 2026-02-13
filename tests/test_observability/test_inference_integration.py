"""Integration tests for track_chat_completions() — full span lifecycle."""

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
    BUD_INFERENCE_RESPONSE_CHOICES,
    BUD_INFERENCE_STREAM,
    BUD_INFERENCE_STREAM_COMPLETED,
    BUD_INFERENCE_TTFT_MS,
    GENAI_RESPONSE_ID,
    GENAI_RESPONSE_MODEL,
    GENAI_RESPONSE_OBJECT,
    GENAI_SYSTEM,
    GENAI_USAGE_INPUT_TOKENS,
    GENAI_USAGE_OUTPUT_TOKENS,
    GENAI_USAGE_TOTAL_TOKENS,
)
from bud.observability._inference_tracker import track_chat_completions

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def traced_env():
    """Set up a traced environment with InMemorySpanExporter.

    Returns (exporter, mock_client) where mock_client is already patched.
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    def _get_tracer(name="bud"):
        return provider.get_tracer(name)

    with (
        patch("bud.observability._track._is_noop", return_value=False),
        patch("bud.observability.get_tracer", side_effect=_get_tracer),
        patch("bud.observability._inference_tracker._is_noop", return_value=False),
    ):
        yield exporter, provider

    provider.shutdown()


def _make_client(create_return_value=None):
    """Create a mock BudClient with chat.completions.create()."""
    client = Mock()
    client.chat.completions = Mock()
    client.chat.completions.create = Mock(return_value=create_return_value)
    client.chat.completions._bud_tracked = False
    # Delete spec so we can set _bud_tracked
    return client


def _make_response():
    """Create a realistic mock ChatCompletion response."""
    usage = Mock()
    usage.prompt_tokens = 10
    usage.completion_tokens = 5
    usage.total_tokens = 15

    message = Mock()
    message.content = "Hello!"
    message.role = "assistant"
    message.tool_calls = None

    choice = Mock()
    choice.index = 0
    choice.finish_reason = "stop"
    choice.message = message

    response = Mock()
    response.id = "chatcmpl-test"
    response.object = "chat.completion"
    response.model = "gpt-4"
    response.created = 1700000000
    response.choices = [choice]
    response.usage = usage
    response.system_fingerprint = "fp_abc"
    return response


def _make_stream_chunks(contents, finish_reason="stop"):
    """Create a list of mock ChatCompletionChunk objects."""
    chunks = []
    for content in contents:
        delta = Mock()
        delta.content = content
        delta.reasoning_content = None
        delta.tool_calls = None

        choice = Mock()
        choice.delta = delta
        choice.finish_reason = None

        chunk = Mock()
        chunk.id = "chatcmpl-stream"
        chunk.model = "gpt-4"
        chunk.choices = [choice]
        chunk.system_fingerprint = None
        # No usage on most chunks
        del chunk.usage
        chunks.append(chunk)

    # Set finish_reason on last chunk
    if chunks:
        chunks[-1].choices[0].finish_reason = finish_reason

    return chunks


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNonStreamingSpan:
    def test_span_created_with_correct_attributes(self, traced_env):
        exporter, _provider = traced_env
        response = _make_response()
        client = _make_client(create_return_value=response)
        track_chat_completions(client)

        result = client.chat.completions.create(
            model="gpt-4", messages=[{"role": "user", "content": "hi"}]
        )

        assert result is response
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "chat"
        attrs = dict(span.attributes)
        assert attrs[GENAI_SYSTEM] == "bud"
        assert attrs[BUD_INFERENCE_OPERATION] == "chat"
        assert attrs[BUD_INFERENCE_STREAM] is False
        assert attrs["gen_ai.request.model"] == "gpt-4"
        assert attrs[GENAI_RESPONSE_ID] == "chatcmpl-test"
        assert attrs[GENAI_RESPONSE_MODEL] == "gpt-4"
        assert attrs[GENAI_USAGE_INPUT_TOKENS] == 10
        assert attrs[GENAI_USAGE_OUTPUT_TOKENS] == 5
        assert attrs[GENAI_USAGE_TOTAL_TOKENS] == 15
        assert attrs[GENAI_RESPONSE_OBJECT] == "chat.completion"
        assert BUD_INFERENCE_RESPONSE_CHOICES in attrs
        choices = json.loads(attrs[BUD_INFERENCE_RESPONSE_CHOICES])
        assert choices[0]["finish_reason"] == "stop"
        assert choices[0]["message"]["content"] == "Hello!"
        assert span.status.status_code == StatusCode.OK


class TestStreamingSpan:
    def test_streaming_span_attributes(self, traced_env):
        exporter, _provider = traced_env
        chunks = _make_stream_chunks(["Hello", " ", "world"])
        client = _make_client(create_return_value=iter(chunks))
        track_chat_completions(client)

        stream = client.chat.completions.create(
            model="gpt-4", messages=[{"role": "user", "content": "hi"}], stream=True
        )

        collected = list(stream)
        assert len(collected) == 3

        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "chat.stream"
        attrs = dict(span.attributes)
        assert attrs[GENAI_SYSTEM] == "bud"
        assert attrs[BUD_INFERENCE_STREAM] is True
        assert attrs[BUD_INFERENCE_CHUNKS] == 3
        assert attrs[BUD_INFERENCE_STREAM_COMPLETED] is True
        assert BUD_INFERENCE_TTFT_MS in attrs
        assert attrs[BUD_INFERENCE_TTFT_MS] >= 0
        assert span.status.status_code == StatusCode.OK

    def test_partial_streaming(self, traced_env):
        exporter, _provider = traced_env
        chunks = _make_stream_chunks(["a", "b", "c", "d"])
        client = _make_client(create_return_value=iter(chunks))
        track_chat_completions(client)

        stream = client.chat.completions.create(model="gpt-4", messages=[], stream=True)

        collected = []
        for chunk in stream:
            collected.append(chunk)
            if len(collected) == 2:
                break

        assert len(collected) == 2

        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        attrs = dict(span.attributes)
        assert attrs[BUD_INFERENCE_CHUNKS] == 2
        assert attrs[BUD_INFERENCE_STREAM_COMPLETED] is False
        # GeneratorExit is NOT an error
        assert span.status.status_code != StatusCode.ERROR


class TestErrorSpan:
    def test_error_recorded_and_reraised(self, traced_env):
        exporter, _provider = traced_env
        client = _make_client()
        client.chat.completions.create.side_effect = RuntimeError("API error")
        track_chat_completions(client)

        with pytest.raises(RuntimeError, match="API error"):
            client.chat.completions.create(model="gpt-4", messages=[])

        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.status.status_code == StatusCode.ERROR
        assert any(e.name == "exception" for e in span.events)


class TestFieldListMode:
    def test_capture_only_model(self, traced_env):
        exporter, _provider = traced_env
        response = _make_response()
        client = _make_client(create_return_value=response)
        track_chat_completions(client, capture_input=["model"])

        client.chat.completions.create(model="gpt-4", temperature=0.5, messages=[])

        spans = exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        assert attrs["gen_ai.request.model"] == "gpt-4"
        assert "gen_ai.request.temperature" not in attrs


class TestCaptureFalse:
    def test_no_input_output_attributes(self, traced_env):
        exporter, _provider = traced_env
        response = _make_response()
        client = _make_client(create_return_value=response)
        track_chat_completions(client, capture_input=False, capture_output=False)

        client.chat.completions.create(model="gpt-4", messages=[])

        spans = exporter.get_finished_spans()
        attrs = dict(spans[0].attributes)
        # Always-on attributes should be present
        assert attrs[GENAI_SYSTEM] == "bud"
        assert attrs[BUD_INFERENCE_OPERATION] == "chat"
        # Request/response attributes should NOT be present
        assert "gen_ai.request.model" not in attrs
        assert GENAI_RESPONSE_ID not in attrs
        assert GENAI_USAGE_INPUT_TOKENS not in attrs


class TestTrackNesting:
    def test_parent_child_with_track_decorator(self, traced_env):
        exporter, _provider = traced_env
        response = _make_response()
        client = _make_client(create_return_value=response)
        track_chat_completions(client)

        from bud.observability._track import track

        @track(name="pipeline")
        def pipeline():
            return client.chat.completions.create(model="gpt-4", messages=[])

        # Patch get_tracer for the @track decorator too
        pipeline()

        spans = exporter.get_finished_spans()
        assert len(spans) == 2

        chat_span = next(s for s in spans if s.name == "chat")
        pipeline_span = next(s for s in spans if s.name == "pipeline")

        assert chat_span.parent is not None
        assert chat_span.parent.span_id == pipeline_span.context.span_id
