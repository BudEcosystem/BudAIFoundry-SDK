"""Unit tests for _responses_tracker module."""

from __future__ import annotations

import json
from unittest.mock import Mock

from bud.observability._genai_attributes import (
    GENAI_CONVERSATION_ID,
    GENAI_INPUT_MESSAGES,
    GENAI_OUTPUT_MESSAGES,
    GENAI_OUTPUT_TYPE,
    GENAI_PROMPT,
    GENAI_PROMPT_ID,
    GENAI_PROMPT_VARIABLES,
    GENAI_PROMPT_VERSION,
    GENAI_REQUEST_INSTRUCTIONS,
    GENAI_RESPONSE_BACKGROUND,
    GENAI_RESPONSE_CREATED,
    GENAI_RESPONSE_ID,
    GENAI_RESPONSE_MAX_OUTPUT_TOKENS,
    GENAI_RESPONSE_MODEL,
    GENAI_RESPONSE_OBJECT,
    GENAI_RESPONSE_PARALLEL_TOOL_CALLS,
    GENAI_RESPONSE_PROMPT,
    GENAI_RESPONSE_REASONING,
    GENAI_RESPONSE_SERVICE_TIER,
    GENAI_RESPONSE_STATUS,
    GENAI_RESPONSE_TEMPERATURE,
    GENAI_RESPONSE_TOOL_CHOICE,
    GENAI_RESPONSE_TOOLS,
    GENAI_SYSTEM_INSTRUCTIONS,
    GENAI_USAGE,
    GENAI_USAGE_INPUT_TOKENS,
    GENAI_USAGE_OUTPUT_TOKENS,
    GENAI_USAGE_TOTAL_TOKENS,
    RESPONSES_SAFE_INPUT_FIELDS,
    RESPONSES_SAFE_OUTPUT_FIELDS,
)
from bud.observability._responses_tracker import (
    _extract_responses_request_attrs,
    _extract_responses_response_attrs,
    _resolve_fields,
    track_responses,
)

# ---------------------------------------------------------------------------
# _resolve_fields
# ---------------------------------------------------------------------------


class TestResolveFields:
    def test_true_returns_safe_defaults(self):
        result = _resolve_fields(True, RESPONSES_SAFE_INPUT_FIELDS)
        assert result is RESPONSES_SAFE_INPUT_FIELDS

    def test_false_returns_none(self):
        result = _resolve_fields(False, RESPONSES_SAFE_INPUT_FIELDS)
        assert result is None

    def test_list_returns_frozenset(self):
        result = _resolve_fields(["model", "input"], RESPONSES_SAFE_INPUT_FIELDS)
        assert result == frozenset({"model", "input"})
        assert isinstance(result, frozenset)


# ---------------------------------------------------------------------------
# _extract_responses_request_attrs
# ---------------------------------------------------------------------------


class TestExtractResponsesRequestAttrs:
    def test_basic_params(self):
        kwargs = {"model": "gpt-4.1", "temperature": 0.7}
        result = _extract_responses_request_attrs(kwargs, RESPONSES_SAFE_INPUT_FIELDS)
        assert result["gen_ai.request.model"] == "gpt-4.1"
        assert result["gen_ai.request.temperature"] == 0.7

    def test_input_string_not_json_serialized(self):
        kwargs = {"input": "Hello world"}
        fields = frozenset({"input"})
        result = _extract_responses_request_attrs(kwargs, fields)
        assert result[GENAI_INPUT_MESSAGES] == "Hello world"

    def test_input_list_json_serialized(self):
        kwargs = {"input": [{"role": "user", "content": "Hello"}]}
        fields = frozenset({"input"})
        result = _extract_responses_request_attrs(kwargs, fields)
        parsed = json.loads(result[GENAI_INPUT_MESSAGES])
        assert parsed[0]["role"] == "user"

    def test_instructions_captured(self):
        kwargs = {"instructions": "Be helpful"}
        fields = frozenset({"instructions"})
        result = _extract_responses_request_attrs(kwargs, fields)
        assert result[GENAI_REQUEST_INSTRUCTIONS] == "Be helpful"

    def test_tools_json_serialized(self):
        kwargs = {"tools": [{"type": "function", "function": {"name": "get_weather"}}]}
        fields = frozenset({"tools"})
        result = _extract_responses_request_attrs(kwargs, fields)
        parsed = json.loads(result["bud.inference.request.tools"])
        assert parsed[0]["type"] == "function"

    def test_tool_choice_dict_serialized(self):
        kwargs = {"tool_choice": {"type": "function", "function": {"name": "get_weather"}}}
        fields = frozenset({"tool_choice"})
        result = _extract_responses_request_attrs(kwargs, fields)
        parsed = json.loads(result["bud.inference.request.tool_choice"])
        assert parsed["type"] == "function"

    def test_tool_choice_string_not_serialized(self):
        kwargs = {"tool_choice": "auto"}
        fields = frozenset({"tool_choice"})
        result = _extract_responses_request_attrs(kwargs, fields)
        assert result["bud.inference.request.tool_choice"] == "auto"

    def test_previous_response_id_mapped(self):
        kwargs = {"previous_response_id": "resp_prev_123"}
        fields = frozenset({"previous_response_id"})
        result = _extract_responses_request_attrs(kwargs, fields)
        assert result[GENAI_CONVERSATION_ID] == "resp_prev_123"

    def test_none_fields_returns_empty(self):
        result = _extract_responses_request_attrs({"model": "gpt-4.1"}, None)
        assert result == {}

    def test_prompt_string_captured(self):
        kwargs = {"prompt": "my-prompt"}
        fields = frozenset({"prompt"})
        result = _extract_responses_request_attrs(kwargs, fields)
        # String prompts go through JSON fields path — not isinstance str for "prompt"
        # because prompt is not in _JSON_FIELDS, it falls through to the else branch
        # Actually prompt dict triggers decomposition, string prompt goes to else
        assert result[GENAI_PROMPT] == "my-prompt"

    def test_prompt_dict_decomposition(self):
        kwargs = {
            "prompt": {
                "id": "prompt-123",
                "version": "v2",
                "variables": {"name": "Alice"},
            }
        }
        fields = frozenset({"prompt"})
        result = _extract_responses_request_attrs(kwargs, fields)
        # Full prompt JSON
        parsed = json.loads(result[GENAI_PROMPT])
        assert parsed["id"] == "prompt-123"
        # Decomposed fields
        assert result[GENAI_PROMPT_ID] == "prompt-123"
        assert result[GENAI_PROMPT_VERSION] == "v2"
        parsed_vars = json.loads(result[GENAI_PROMPT_VARIABLES])
        assert parsed_vars["name"] == "Alice"

    def test_prompt_dict_partial_fields(self):
        kwargs = {"prompt": {"id": "prompt-456"}}
        fields = frozenset({"prompt"})
        result = _extract_responses_request_attrs(kwargs, fields)
        assert result[GENAI_PROMPT_ID] == "prompt-456"
        assert GENAI_PROMPT_VERSION not in result
        assert GENAI_PROMPT_VARIABLES not in result

    def test_metadata_json_serialized(self):
        kwargs = {"metadata": {"key": "value"}}
        fields = frozenset({"metadata"})
        result = _extract_responses_request_attrs(kwargs, fields)
        parsed = json.loads(result["gen_ai.request.metadata"])
        assert parsed["key"] == "value"

    def test_response_format_json_serialized(self):
        kwargs = {"response_format": {"type": "json_object"}}
        fields = frozenset({"response_format"})
        result = _extract_responses_request_attrs(kwargs, fields)
        parsed = json.loads(result["gen_ai.request.response_format"])
        assert parsed["type"] == "json_object"

    def test_modalities_json_serialized(self):
        kwargs = {"modalities": ["text", "audio"]}
        fields = frozenset({"modalities"})
        result = _extract_responses_request_attrs(kwargs, fields)
        parsed = json.loads(result["gen_ai.request.modalities"])
        assert parsed == ["text", "audio"]


# ---------------------------------------------------------------------------
# _extract_responses_response_attrs
# ---------------------------------------------------------------------------


def _mock_responses_response(
    id: str = "resp_123",
    model: str = "gpt-4.1",
    status: str = "completed",
    created_at: float = 1700000000.0,
    input_tokens: int = 10,
    output_tokens: int = 5,
    total_tokens: int = 15,
    object: str = "response",
    output: list | None = None,
    instructions: str | None = "You are a helpful assistant",
    background: bool | None = None,
    parallel_tool_calls: bool | None = None,
    max_output_tokens: int | None = None,
    temperature: float | None = 1.0,
    top_p: float | None = 1.0,
    service_tier: str | None = None,
    tools: list | None = None,
    tool_choice: str | None = None,
    reasoning: dict | None = None,
    text: dict | None = None,
    prompt: dict | None = None,
):
    """Create a mock openai.types.responses.Response-like object."""
    usage = Mock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens
    usage.total_tokens = total_tokens
    # Make usage serializable via model_dump
    usage.model_dump = Mock(return_value={
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    })

    if output is None:
        output_item = Mock()
        output_item.model_dump = Mock(return_value={
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "Hello!"}],
        })
        output = [output_item]

    response = Mock()
    response.id = id
    response.model = model
    response.status = status
    response.created_at = created_at
    response.usage = usage
    response.object = object
    response.output = output
    response.instructions = instructions
    response.background = background
    response.parallel_tool_calls = parallel_tool_calls
    response.max_output_tokens = max_output_tokens
    response.temperature = temperature
    response.top_p = top_p
    response.service_tier = service_tier
    response.tools = tools
    response.tool_choice = tool_choice
    response.reasoning = reasoning
    response.text = text
    response.prompt = prompt
    return response


class TestExtractResponsesResponseAttrs:
    def test_full_extraction(self):
        response = _mock_responses_response()
        result = _extract_responses_response_attrs(response, RESPONSES_SAFE_OUTPUT_FIELDS)
        assert result[GENAI_RESPONSE_ID] == "resp_123"
        assert result[GENAI_RESPONSE_MODEL] == "gpt-4.1"
        assert result[GENAI_RESPONSE_STATUS] == "completed"
        assert result[GENAI_RESPONSE_CREATED] == 1700000000.0
        assert result[GENAI_USAGE_INPUT_TOKENS] == 10
        assert result[GENAI_USAGE_OUTPUT_TOKENS] == 5
        assert result[GENAI_USAGE_TOTAL_TOKENS] == 15
        assert result[GENAI_RESPONSE_OBJECT] == "response"

    def test_output_messages_captured(self):
        response = _mock_responses_response()
        result = _extract_responses_response_attrs(response, RESPONSES_SAFE_OUTPUT_FIELDS)
        parsed = json.loads(result[GENAI_OUTPUT_MESSAGES])
        assert isinstance(parsed, list)
        assert parsed[0]["type"] == "message"

    def test_instructions_string_captured_as_is(self):
        response = _mock_responses_response(instructions="Be concise")
        result = _extract_responses_response_attrs(response, RESPONSES_SAFE_OUTPUT_FIELDS)
        # String instructions should be stored as-is, not JSON-serialized
        assert result[GENAI_SYSTEM_INSTRUCTIONS] == "Be concise"

    def test_instructions_list_json_serialized(self):
        instructions = [{"type": "message", "content": "Be concise"}]
        response = _mock_responses_response()
        response.instructions = instructions
        result = _extract_responses_response_attrs(response, RESPONSES_SAFE_OUTPUT_FIELDS)
        parsed = json.loads(result[GENAI_SYSTEM_INSTRUCTIONS])
        assert parsed == instructions

    def test_usage_full_json(self):
        response = _mock_responses_response()
        result = _extract_responses_response_attrs(response, RESPONSES_SAFE_OUTPUT_FIELDS)
        parsed = json.loads(result[GENAI_USAGE])
        assert parsed["input_tokens"] == 10
        assert parsed["output_tokens"] == 5
        assert parsed["total_tokens"] == 15

    def test_none_usage(self):
        response = _mock_responses_response()
        response.usage = None
        result = _extract_responses_response_attrs(response, RESPONSES_SAFE_OUTPUT_FIELDS)
        assert GENAI_USAGE_INPUT_TOKENS not in result
        assert GENAI_USAGE not in result

    def test_none_fields_returns_empty(self):
        response = _mock_responses_response()
        result = _extract_responses_response_attrs(response, None)
        assert result == {}

    def test_selective_fields(self):
        response = _mock_responses_response()
        fields = frozenset({"id", "usage"})
        result = _extract_responses_response_attrs(response, fields)
        assert result[GENAI_RESPONSE_ID] == "resp_123"
        assert result[GENAI_USAGE_INPUT_TOKENS] == 10
        assert GENAI_RESPONSE_MODEL not in result
        assert GENAI_RESPONSE_STATUS not in result

    def test_datetime_created_at(self):
        """Test that datetime objects are converted to float timestamps."""
        response = _mock_responses_response()
        mock_dt = Mock()
        mock_dt.timestamp.return_value = 1700000000.0
        response.created_at = mock_dt
        fields = frozenset({"created_at"})
        result = _extract_responses_response_attrs(response, fields)
        assert result[GENAI_RESPONSE_CREATED] == 1700000000.0

    def test_background_captured(self):
        response = _mock_responses_response(background=True)
        fields = frozenset({"background"})
        result = _extract_responses_response_attrs(response, fields)
        assert result[GENAI_RESPONSE_BACKGROUND] is True

    def test_parallel_tool_calls_captured(self):
        response = _mock_responses_response(parallel_tool_calls=True)
        fields = frozenset({"parallel_tool_calls"})
        result = _extract_responses_response_attrs(response, fields)
        assert result[GENAI_RESPONSE_PARALLEL_TOOL_CALLS] is True

    def test_max_output_tokens_captured(self):
        response = _mock_responses_response(max_output_tokens=4096)
        fields = frozenset({"max_output_tokens"})
        result = _extract_responses_response_attrs(response, fields)
        assert result[GENAI_RESPONSE_MAX_OUTPUT_TOKENS] == 4096

    def test_temperature_captured(self):
        response = _mock_responses_response(temperature=0.5)
        fields = frozenset({"temperature"})
        result = _extract_responses_response_attrs(response, fields)
        assert result[GENAI_RESPONSE_TEMPERATURE] == 0.5

    def test_service_tier_captured(self):
        response = _mock_responses_response(service_tier="default")
        fields = frozenset({"service_tier"})
        result = _extract_responses_response_attrs(response, fields)
        assert result[GENAI_RESPONSE_SERVICE_TIER] == "default"

    def test_tool_choice_string_not_double_quoted(self):
        """String tool_choice should be stored as-is, not JSON-serialized."""
        response = _mock_responses_response(tool_choice="auto")
        fields = frozenset({"tool_choice"})
        result = _extract_responses_response_attrs(response, fields)
        assert result[GENAI_RESPONSE_TOOL_CHOICE] == "auto"

    def test_tool_choice_dict_json_serialized(self):
        tc = {"type": "function", "function": {"name": "get_weather"}}
        response = _mock_responses_response()
        response.tool_choice = Mock()
        response.tool_choice.model_dump = Mock(return_value=tc)
        fields = frozenset({"tool_choice"})
        result = _extract_responses_response_attrs(response, fields)
        parsed = json.loads(result[GENAI_RESPONSE_TOOL_CHOICE])
        assert parsed["type"] == "function"

    def test_none_optional_fields_omitted(self):
        """Fields that are None on the response should not appear in attrs."""
        response = _mock_responses_response(
            background=None,
            parallel_tool_calls=None,
            max_output_tokens=None,
            service_tier=None,
            tools=None,
            tool_choice=None,
            reasoning=None,
            text=None,
            prompt=None,
        )
        result = _extract_responses_response_attrs(response, RESPONSES_SAFE_OUTPUT_FIELDS)
        assert GENAI_RESPONSE_BACKGROUND not in result
        assert GENAI_RESPONSE_PARALLEL_TOOL_CALLS not in result
        assert GENAI_RESPONSE_MAX_OUTPUT_TOKENS not in result
        assert GENAI_RESPONSE_SERVICE_TIER not in result
        assert GENAI_RESPONSE_TOOLS not in result
        assert GENAI_RESPONSE_TOOL_CHOICE not in result
        assert GENAI_RESPONSE_REASONING not in result
        assert GENAI_OUTPUT_TYPE not in result
        assert GENAI_RESPONSE_PROMPT not in result


# ---------------------------------------------------------------------------
# track_responses — idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_second_call_is_noop(self):
        client = Mock()
        client.responses.create = Mock(return_value="original")
        client.responses._bud_tracked = False

        result = track_responses(client)
        assert result is client
        first_create = client.responses.create

        assert client.responses._bud_tracked is True

        result2 = track_responses(client)
        assert result2 is client
        assert client.responses.create is first_create
