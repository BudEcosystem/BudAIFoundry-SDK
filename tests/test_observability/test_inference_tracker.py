"""Unit tests for _inference_tracker module."""

from __future__ import annotations

import json
from unittest.mock import Mock

from bud.observability._genai_attributes import (
    BUD_INFERENCE_REQUEST_TOOL_CHOICE,
    BUD_INFERENCE_REQUEST_USER,
    BUD_INFERENCE_RESPONSE_CHOICES,
    CHAT_SAFE_INPUT_FIELDS,
    CHAT_SAFE_OUTPUT_FIELDS,
    GENAI_CONTENT_PROMPT,
    GENAI_RESPONSE_CREATED,
    GENAI_RESPONSE_ID,
    GENAI_RESPONSE_MODEL,
    GENAI_RESPONSE_OBJECT,
    GENAI_RESPONSE_SYSTEM_FINGERPRINT,
    GENAI_USAGE_INPUT_TOKENS,
    GENAI_USAGE_OUTPUT_TOKENS,
    GENAI_USAGE_TOTAL_TOKENS,
)
from bud.observability._inference_tracker import (
    _aggregate_stream_response,
    _extract_chat_request_attrs,
    _extract_chat_response_attrs,
    _resolve_fields,
    track_chat_completions,
)

# ---------------------------------------------------------------------------
# _resolve_fields
# ---------------------------------------------------------------------------


class TestResolveFields:
    def test_true_returns_safe_defaults(self):
        result = _resolve_fields(True, CHAT_SAFE_INPUT_FIELDS)
        assert result is CHAT_SAFE_INPUT_FIELDS

    def test_false_returns_none(self):
        result = _resolve_fields(False, CHAT_SAFE_INPUT_FIELDS)
        assert result is None

    def test_list_returns_frozenset(self):
        result = _resolve_fields(["model", "messages"], CHAT_SAFE_INPUT_FIELDS)
        assert result == frozenset({"model", "messages"})
        assert isinstance(result, frozenset)


# ---------------------------------------------------------------------------
# _extract_chat_request_attrs
# ---------------------------------------------------------------------------


class TestExtractChatRequestAttrs:
    def test_safe_defaults(self):
        kwargs = {
            "model": "gpt-4",
            "temperature": 0.7,
            "messages": [{"role": "user", "content": "hi"}],
        }
        result = _extract_chat_request_attrs(kwargs, CHAT_SAFE_INPUT_FIELDS)
        assert result["gen_ai.request.model"] == "gpt-4"
        assert result["gen_ai.request.temperature"] == 0.7
        # Messages ARE now captured by default (True captures everything)
        assert GENAI_CONTENT_PROMPT in result

    def test_with_messages(self):
        msgs = [{"role": "user", "content": "hello"}]
        kwargs = {"model": "gpt-4", "messages": msgs}
        fields = frozenset({"model", "messages"})
        result = _extract_chat_request_attrs(kwargs, fields)
        assert "gen_ai.request.model" in result
        assert GENAI_CONTENT_PROMPT in result

    def test_none_fields_returns_empty(self):
        result = _extract_chat_request_attrs({"model": "gpt-4"}, None)
        assert result == {}

    def test_unmapped_kwarg(self):
        kwargs = {"model": "gpt-4", "custom_param": "value"}
        fields = frozenset({"model", "custom_param"})
        result = _extract_chat_request_attrs(kwargs, fields)
        assert result["bud.inference.request.custom_param"] == "value"

    def test_stop_list_serialized(self):
        kwargs = {"stop": ["\n", "END"]}
        fields = frozenset({"stop"})
        result = _extract_chat_request_attrs(kwargs, fields)
        assert result["gen_ai.request.stop_sequences"] == '["\\n", "END"]'

    def test_stop_string_not_serialized(self):
        kwargs = {"stop": "\n"}
        fields = frozenset({"stop"})
        result = _extract_chat_request_attrs(kwargs, fields)
        assert result["gen_ai.request.stop_sequences"] == "\n"


# ---------------------------------------------------------------------------
# _extract_chat_response_attrs
# ---------------------------------------------------------------------------


def _mock_response(
    id: str = "chatcmpl-123",
    object: str = "chat.completion",
    model: str = "gpt-4",
    created: int = 1700000000,
    finish_reason: str = "stop",
    content: str = "Hello!",
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
    total_tokens: int = 15,
    system_fingerprint: str | None = "fp_abc",
    tool_calls: list | None = None,
):
    """Create a mock ChatCompletion-like object."""
    usage = Mock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    usage.total_tokens = total_tokens

    message = Mock()
    message.content = content
    message.tool_calls = tool_calls
    message.role = "assistant"

    choice = Mock()
    choice.index = 0
    choice.finish_reason = finish_reason
    choice.message = message

    response = Mock()
    response.id = id
    response.object = object
    response.model = model
    response.created = created
    response.choices = [choice]
    response.usage = usage
    response.system_fingerprint = system_fingerprint
    return response


class TestExtractChatResponseAttrs:
    def test_full_extraction(self):
        response = _mock_response()
        result = _extract_chat_response_attrs(response, CHAT_SAFE_OUTPUT_FIELDS)
        assert result[GENAI_RESPONSE_ID] == "chatcmpl-123"
        assert result[GENAI_RESPONSE_OBJECT] == "chat.completion"
        assert result[GENAI_RESPONSE_MODEL] == "gpt-4"
        assert result[GENAI_RESPONSE_CREATED] == 1700000000
        assert result[GENAI_USAGE_INPUT_TOKENS] == 10
        assert result[GENAI_USAGE_OUTPUT_TOKENS] == 5
        assert result[GENAI_USAGE_TOTAL_TOKENS] == 15
        assert result[GENAI_RESPONSE_SYSTEM_FINGERPRINT] == "fp_abc"
        assert BUD_INFERENCE_RESPONSE_CHOICES in result

    def test_content_extraction(self):
        response = _mock_response(content="Hello world")
        fields = frozenset({"choices"})
        result = _extract_chat_response_attrs(response, fields)
        assert BUD_INFERENCE_RESPONSE_CHOICES in result
        choices_data = json.loads(result[BUD_INFERENCE_RESPONSE_CHOICES])
        assert choices_data[0]["message"]["content"] == "Hello world"

    def test_none_usage(self):
        response = _mock_response()
        response.usage = None
        result = _extract_chat_response_attrs(response, CHAT_SAFE_OUTPUT_FIELDS)
        assert GENAI_USAGE_INPUT_TOKENS not in result
        assert GENAI_USAGE_OUTPUT_TOKENS not in result

    def test_none_fields_returns_empty(self):
        response = _mock_response()
        result = _extract_chat_response_attrs(response, None)
        assert result == {}

    def test_system_fingerprint_none_skipped(self):
        response = _mock_response(system_fingerprint=None)
        result = _extract_chat_response_attrs(response, CHAT_SAFE_OUTPUT_FIELDS)
        assert GENAI_RESPONSE_SYSTEM_FINGERPRINT not in result

    def test_tool_calls_captured(self):
        tc = [{"id": "call_1", "type": "function", "function": {"name": "get_weather", "arguments": "{}"}}]
        response = _mock_response(tool_calls=tc)
        fields = frozenset({"choices"})
        result = _extract_chat_response_attrs(response, fields)
        assert BUD_INFERENCE_RESPONSE_CHOICES in result
        choices_data = json.loads(result[BUD_INFERENCE_RESPONSE_CHOICES])
        assert choices_data[0]["message"]["tool_calls"] is not None

    def test_tool_calls_none_skipped(self):
        response = _mock_response(tool_calls=None)
        fields = frozenset({"choices"})
        result = _extract_chat_response_attrs(response, fields)
        assert BUD_INFERENCE_RESPONSE_CHOICES in result
        choices_data = json.loads(result[BUD_INFERENCE_RESPONSE_CHOICES])
        assert choices_data[0]["message"]["tool_calls"] is None

    def test_object_captured(self):
        response = _mock_response(object="chat.completion")
        fields = frozenset({"object"})
        result = _extract_chat_response_attrs(response, fields)
        assert result[GENAI_RESPONSE_OBJECT] == "chat.completion"


# ---------------------------------------------------------------------------
# _extract_chat_request_attrs — new fields
# ---------------------------------------------------------------------------


class TestExtractChatRequestAttrsNewFields:
    def test_tool_choice_dict_serialized(self):
        kwargs = {"tool_choice": {"type": "function", "function": {"name": "get_weather"}}}
        fields = frozenset({"tool_choice"})
        result = _extract_chat_request_attrs(kwargs, fields)
        assert BUD_INFERENCE_REQUEST_TOOL_CHOICE in result
        # Should be JSON-serialized since it's a dict
        parsed = json.loads(result[BUD_INFERENCE_REQUEST_TOOL_CHOICE])
        assert parsed["type"] == "function"

    def test_tool_choice_string_not_serialized(self):
        kwargs = {"tool_choice": "auto"}
        fields = frozenset({"tool_choice"})
        result = _extract_chat_request_attrs(kwargs, fields)
        assert result[BUD_INFERENCE_REQUEST_TOOL_CHOICE] == "auto"

    def test_user_captured(self):
        kwargs = {"model": "gpt-4", "user": "user-123"}
        fields = frozenset({"model", "user"})
        result = _extract_chat_request_attrs(kwargs, fields)
        assert result[BUD_INFERENCE_REQUEST_USER] == "user-123"


# ---------------------------------------------------------------------------
# _aggregate_stream_response
# ---------------------------------------------------------------------------


def _mock_chunk(
    id: str = "chatcmpl-123",
    model: str = "gpt-4",
    content: str | None = None,
    reasoning_content: str | None = None,
    finish_reason: str | None = None,
    system_fingerprint: str | None = None,
    usage: Mock | None = None,
):
    """Create a mock ChatCompletionChunk-like object."""
    delta = Mock()
    delta.content = content
    delta.reasoning_content = reasoning_content
    delta.tool_calls = None

    choice = Mock()
    choice.delta = delta
    choice.finish_reason = finish_reason

    chunk = Mock()
    chunk.id = id
    chunk.model = model
    chunk.choices = [choice]
    chunk.system_fingerprint = system_fingerprint

    if usage is not None:
        chunk.usage = usage
    else:
        # Simulate no usage attribute via spec
        del chunk.usage

    return chunk


class TestAggregateStreamResponse:
    def test_basic_content_join(self):
        chunks = [
            _mock_chunk(content="Hello"),
            _mock_chunk(content=" "),
            _mock_chunk(content="world"),
            _mock_chunk(content=None, finish_reason="stop"),
        ]
        fields = frozenset({"choices"})
        result = _aggregate_stream_response(chunks, fields)
        assert BUD_INFERENCE_RESPONSE_CHOICES in result
        choices_data = json.loads(result[BUD_INFERENCE_RESPONSE_CHOICES])
        assert choices_data[0]["message"]["content"] == "Hello world"
        assert choices_data[0]["finish_reason"] == "stop"

    def test_reasoning_content(self):
        chunks = [
            _mock_chunk(reasoning_content="Think"),
            _mock_chunk(reasoning_content="ing..."),
            _mock_chunk(content="Answer"),
        ]
        fields = frozenset({"choices"})
        result = _aggregate_stream_response(chunks, fields)
        choices_data = json.loads(result[BUD_INFERENCE_RESPONSE_CHOICES])
        content = choices_data[0]["message"]["content"]
        assert "Answer" in content
        assert "Thinking..." in content

    def test_usage_from_last_chunk(self):
        usage_mock = Mock()
        usage_mock.prompt_tokens = 15
        usage_mock.completion_tokens = 8
        usage_mock.total_tokens = 23
        chunks = [
            _mock_chunk(content="Hello"),
            _mock_chunk(content=" world", usage=usage_mock),
        ]
        fields = frozenset({"usage"})
        result = _aggregate_stream_response(chunks, fields)
        assert result[GENAI_USAGE_INPUT_TOKENS] == 15
        assert result[GENAI_USAGE_OUTPUT_TOKENS] == 8
        assert result[GENAI_USAGE_TOTAL_TOKENS] == 23

    def test_empty_chunks(self):
        result = _aggregate_stream_response([], CHAT_SAFE_OUTPUT_FIELDS)
        assert result == {}

    def test_none_fields(self):
        chunks = [_mock_chunk(content="test")]
        result = _aggregate_stream_response(chunks, None)
        assert result == {}

    def test_id_and_model_from_first_chunk(self):
        chunks = [
            _mock_chunk(id="id-1", model="model-a"),
            _mock_chunk(id="id-2", model="model-b"),
        ]
        fields = frozenset({"id", "model"})
        result = _aggregate_stream_response(chunks, fields)
        assert result[GENAI_RESPONSE_ID] == "id-1"
        assert result[GENAI_RESPONSE_MODEL] == "model-a"

    def test_total_tokens_from_stream(self):
        usage_mock = Mock()
        usage_mock.prompt_tokens = 15
        usage_mock.completion_tokens = 8
        usage_mock.total_tokens = 23
        chunks = [
            _mock_chunk(content="Hello"),
            _mock_chunk(content=" world", usage=usage_mock),
        ]
        fields = frozenset({"usage"})
        result = _aggregate_stream_response(chunks, fields)
        assert result[GENAI_USAGE_INPUT_TOKENS] == 15
        assert result[GENAI_USAGE_OUTPUT_TOKENS] == 8
        assert result[GENAI_USAGE_TOTAL_TOKENS] == 23

    def test_tool_calls_from_stream(self):
        delta1 = Mock()
        delta1.content = None
        delta1.reasoning_content = None
        delta1.tool_calls = [{"index": 0, "id": "call_1", "function": {"name": "get_weather", "arguments": ""}}]

        delta2 = Mock()
        delta2.content = None
        delta2.reasoning_content = None
        delta2.tool_calls = [{"index": 0, "function": {"arguments": '{"city":"NYC"}'}}]

        choice1 = Mock()
        choice1.delta = delta1
        choice1.finish_reason = None
        chunk1 = Mock()
        chunk1.id = "chatcmpl-123"
        chunk1.model = "gpt-4"
        chunk1.choices = [choice1]
        chunk1.system_fingerprint = None
        del chunk1.usage

        choice2 = Mock()
        choice2.delta = delta2
        choice2.finish_reason = None
        chunk2 = Mock()
        chunk2.id = "chatcmpl-123"
        chunk2.model = "gpt-4"
        chunk2.choices = [choice2]
        chunk2.system_fingerprint = None
        del chunk2.usage

        fields = frozenset({"choices"})
        result = _aggregate_stream_response([chunk1, chunk2], fields)
        assert BUD_INFERENCE_RESPONSE_CHOICES in result
        choices_data = json.loads(result[BUD_INFERENCE_RESPONSE_CHOICES])
        assert choices_data[0]["message"]["tool_calls"] is not None


# ---------------------------------------------------------------------------
# track_chat_completions — idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_second_call_is_noop(self):
        client = Mock()
        client.chat.completions.create = Mock(return_value="original")
        client.chat.completions._bud_tracked = False

        # First call patches
        result = track_chat_completions(client)
        assert result is client
        first_create = client.chat.completions.create

        # Mark as tracked (done by track_chat_completions)
        assert client.chat.completions._bud_tracked is True

        # Second call is no-op
        result2 = track_chat_completions(client)
        assert result2 is client
        assert client.chat.completions.create is first_create
