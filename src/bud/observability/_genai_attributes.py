"""OpenTelemetry GenAI Semantic Convention constants.

See: https://opentelemetry.io/docs/specs/semconv/gen-ai/

This module contains only string constants and data structures — no logic,
no external imports.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------

GENAI_SYSTEM = "gen_ai.system"

# ---------------------------------------------------------------------------
# Request attributes
# ---------------------------------------------------------------------------

GENAI_REQUEST_MODEL = "gen_ai.request.model"
GENAI_REQUEST_TEMPERATURE = "gen_ai.request.temperature"
GENAI_REQUEST_TOP_P = "gen_ai.request.top_p"
GENAI_REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens"
GENAI_REQUEST_STOP_SEQUENCES = "gen_ai.request.stop_sequences"
GENAI_REQUEST_PRESENCE_PENALTY = "gen_ai.request.presence_penalty"
GENAI_REQUEST_FREQUENCY_PENALTY = "gen_ai.request.frequency_penalty"

# ---------------------------------------------------------------------------
# Response attributes
# ---------------------------------------------------------------------------

GENAI_RESPONSE_ID = "gen_ai.response.id"
GENAI_RESPONSE_OBJECT = "gen_ai.response.object"
GENAI_RESPONSE_MODEL = "gen_ai.response.model"
GENAI_RESPONSE_CREATED = "gen_ai.response.created"
GENAI_RESPONSE_SYSTEM_FINGERPRINT = "gen_ai.response.system_fingerprint"

# ---------------------------------------------------------------------------
# Usage attributes
# ---------------------------------------------------------------------------

GENAI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
GENAI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
GENAI_USAGE_TOTAL_TOKENS = "gen_ai.usage.total_tokens"

# ---------------------------------------------------------------------------
# Content attributes (PII — opt-in only)
# ---------------------------------------------------------------------------

GENAI_CONTENT_PROMPT = "gen_ai.content.prompt"

# ---------------------------------------------------------------------------
# Bud-specific extensions
# ---------------------------------------------------------------------------

BUD_INFERENCE_STREAM = "bud.inference.stream"
BUD_INFERENCE_TTFT_MS = "bud.inference.ttft_ms"
BUD_INFERENCE_CHUNKS = "bud.inference.chunks"
BUD_INFERENCE_STREAM_COMPLETED = "bud.inference.stream_completed"
BUD_INFERENCE_OPERATION = "bud.inference.operation"

BUD_INFERENCE_REQUEST_USER = "bud.inference.request.user"
BUD_INFERENCE_REQUEST_TOOL_CHOICE = "bud.inference.request.tool_choice"
BUD_INFERENCE_REQUEST_TOOLS = "bud.inference.request.tools"
BUD_INFERENCE_RESPONSE_CHOICES = "bud.inference.response.choices"

# ---------------------------------------------------------------------------
# Mapping: create() kwarg name → OTel attribute key
# ---------------------------------------------------------------------------

CHAT_INPUT_ATTR_MAP: dict[str, str] = {
    "model": GENAI_REQUEST_MODEL,
    "temperature": GENAI_REQUEST_TEMPERATURE,
    "top_p": GENAI_REQUEST_TOP_P,
    "max_tokens": GENAI_REQUEST_MAX_TOKENS,
    "stop": GENAI_REQUEST_STOP_SEQUENCES,
    "presence_penalty": GENAI_REQUEST_PRESENCE_PENALTY,
    "frequency_penalty": GENAI_REQUEST_FREQUENCY_PENALTY,
    "stream": BUD_INFERENCE_STREAM,
    "messages": GENAI_CONTENT_PROMPT,
    "tools": BUD_INFERENCE_REQUEST_TOOLS,
    "tool_choice": BUD_INFERENCE_REQUEST_TOOL_CHOICE,
    "user": BUD_INFERENCE_REQUEST_USER,
}

# ---------------------------------------------------------------------------
# Default field sets (capture everything)
# ---------------------------------------------------------------------------

CHAT_DEFAULT_INPUT_FIELDS: frozenset[str] = frozenset(
    {
        "model",
        "temperature",
        "top_p",
        "max_tokens",
        "stop",
        "presence_penalty",
        "frequency_penalty",
        "stream",
        "tool_choice",
        "messages",
        "tools",
        "user",
    }
)

CHAT_DEFAULT_OUTPUT_FIELDS: frozenset[str] = frozenset(
    {
        "id",
        "object",
        "created",
        "model",
        "choices",
        "usage",
        "system_fingerprint",
    }
)

# Backward compatibility aliases
CHAT_SAFE_INPUT_FIELDS = CHAT_DEFAULT_INPUT_FIELDS
CHAT_SAFE_OUTPUT_FIELDS = CHAT_DEFAULT_OUTPUT_FIELDS

# ---------------------------------------------------------------------------
# Responses API attributes
# ---------------------------------------------------------------------------

GENAI_OPERATION_NAME = "gen_ai.operation.name"
GENAI_CONVERSATION_ID = "gen_ai.conversation.id"
GENAI_RESPONSE_STATUS = "gen_ai.response.status"

# Gateway-aligned attributes
GENAI_INPUT_MESSAGES = "gen_ai.input.messages"
GENAI_REQUEST_INSTRUCTIONS = "gen_ai.request.instructions"
GENAI_PROMPT = "gen_ai.prompt"
GENAI_PROMPT_ID = "gen_ai.prompt.id"
GENAI_PROMPT_VERSION = "gen_ai.prompt.version"
GENAI_PROMPT_VARIABLES = "gen_ai.prompt.variables"
GENAI_OUTPUT_MESSAGES = "gen_ai.output.messages"
GENAI_SYSTEM_INSTRUCTIONS = "gen_ai.system.instructions"
GENAI_RESPONSE_REASONING = "gen_ai.response.reasoning"
GENAI_OUTPUT_TYPE = "gen_ai.output.type"
GENAI_RESPONSE_TOOLS = "gen_ai.response.tools"
GENAI_RESPONSE_TOOL_CHOICE = "gen_ai.response.tool_choice"
GENAI_RESPONSE_PROMPT = "gen_ai.response.prompt"
GENAI_RESPONSE_BACKGROUND = "gen_ai.response.background"
GENAI_RESPONSE_PARALLEL_TOOL_CALLS = "gen_ai.response.parallel_tool_calls"
GENAI_RESPONSE_MAX_OUTPUT_TOKENS = "gen_ai.response.max_output_tokens"
GENAI_RESPONSE_TEMPERATURE = "gen_ai.response.temperature"
GENAI_RESPONSE_TOP_P = "gen_ai.response.top_p"
GENAI_RESPONSE_SERVICE_TIER = "gen_ai.openai.response.service_tier"
GENAI_USAGE = "gen_ai.usage"

# ---------------------------------------------------------------------------
# Mapping: Responses create() kwarg name -> OTel attribute key
# ---------------------------------------------------------------------------

RESPONSES_INPUT_ATTR_MAP: dict[str, str] = {
    # Existing (unchanged)
    "model": GENAI_REQUEST_MODEL,
    "temperature": GENAI_REQUEST_TEMPERATURE,
    "top_p": GENAI_REQUEST_TOP_P,
    "max_output_tokens": GENAI_REQUEST_MAX_TOKENS,
    "stream": BUD_INFERENCE_STREAM,
    "tools": BUD_INFERENCE_REQUEST_TOOLS,
    "tool_choice": BUD_INFERENCE_REQUEST_TOOL_CHOICE,
    "user": BUD_INFERENCE_REQUEST_USER,
    "previous_response_id": GENAI_CONVERSATION_ID,
    # Gateway-aligned keys
    "input": GENAI_INPUT_MESSAGES,
    "instructions": GENAI_REQUEST_INSTRUCTIONS,
    "prompt": GENAI_PROMPT,
    # New mappings (match gateway)
    "reasoning": "gen_ai.request.reasoning",
    "include": "gen_ai.request.include",
    "store": "gen_ai.request.store",
    "service_tier": "gen_ai.request.service_tier",
    "truncation": "gen_ai.request.truncation",
    "response_format": "gen_ai.request.response_format",
    "metadata": "gen_ai.request.metadata",
    "parallel_tool_calls": "gen_ai.request.parallel_tool_calls",
    "max_tool_calls": "gen_ai.request.max_tool_calls",
    "background": "gen_ai.request.background",
    "modalities": "gen_ai.request.modalities",
    "stream_options": "gen_ai.request.stream_options",
}

# ---------------------------------------------------------------------------
# Responses API default field sets
# ---------------------------------------------------------------------------

RESPONSES_DEFAULT_INPUT_FIELDS: frozenset[str] = frozenset(
    {
        "model",
        "temperature",
        "top_p",
        "max_output_tokens",
        "stream",
        "tool_choice",
        "input",
        "instructions",
        "tools",
        "user",
        "prompt",
        "previous_response_id",
        "reasoning",
        "store",
        "service_tier",
        "truncation",
        "include",
        "response_format",
        "metadata",
        "parallel_tool_calls",
        "max_tool_calls",
        "background",
        "modalities",
        "stream_options",
    }
)

RESPONSES_DEFAULT_OUTPUT_FIELDS: frozenset[str] = frozenset(
    {
        "id",
        "status",
        "created_at",
        "model",
        "usage",
        "object",
        "output",
        "instructions",
        "background",
        "parallel_tool_calls",
        "max_output_tokens",
        "temperature",
        "top_p",
        "service_tier",
        "tools",
        "tool_choice",
        "reasoning",
        "text",
        "prompt",
    }
)

# Backward compatibility aliases
RESPONSES_SAFE_INPUT_FIELDS = RESPONSES_DEFAULT_INPUT_FIELDS
RESPONSES_SAFE_OUTPUT_FIELDS = RESPONSES_DEFAULT_OUTPUT_FIELDS
