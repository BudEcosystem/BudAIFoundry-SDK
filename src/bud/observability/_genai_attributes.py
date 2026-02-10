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
