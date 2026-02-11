"""Inference-level tracing for the Responses API.

Instruments ``client.responses.create()`` with OTel spans for both
streaming and non-streaming calls. Records request parameters, response
metadata, token usage, and time-to-first-token as span attributes following
the OpenTelemetry GenAI Semantic Conventions.

Usage::

    from bud import BudClient
    from bud.observability import track_responses

    client = BudClient(api_key="...")
    track_responses(client)

    response = client.responses.create(model="gpt-4.1", input="Hello!")
"""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any

from bud.observability._genai_attributes import (
    BUD_INFERENCE_CHUNKS,
    BUD_INFERENCE_OPERATION,
    BUD_INFERENCE_STREAM,
    BUD_INFERENCE_STREAM_COMPLETED,
    BUD_INFERENCE_TTFT_MS,
    GENAI_CONVERSATION_ID,
    GENAI_OPERATION_NAME,
    GENAI_OUTPUT_MESSAGES,
    GENAI_OUTPUT_TYPE,
    GENAI_PROMPT_ID,
    GENAI_PROMPT_VARIABLES,
    GENAI_PROMPT_VERSION,
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
    GENAI_RESPONSE_TOP_P,
    GENAI_SYSTEM,
    GENAI_SYSTEM_INSTRUCTIONS,
    GENAI_USAGE,
    GENAI_USAGE_INPUT_TOKENS,
    GENAI_USAGE_OUTPUT_TOKENS,
    GENAI_USAGE_TOTAL_TOKENS,
    RESPONSES_INPUT_ATTR_MAP,
    RESPONSES_SAFE_INPUT_FIELDS,
    RESPONSES_SAFE_OUTPUT_FIELDS,
)
from bud.observability._track import _is_noop, _record_exception, _set_ok_status

if TYPE_CHECKING:
    from bud.client import BudClient

logger = logging.getLogger("bud.observability")

# ---------------------------------------------------------------------------
# Type alias
# ---------------------------------------------------------------------------

FieldCapture = bool | list[str]

# ---------------------------------------------------------------------------
# Field resolution
# ---------------------------------------------------------------------------


def _resolve_fields(
    capture: FieldCapture,
    safe_defaults: frozenset[str],
) -> frozenset[str] | None:
    """Convert user-facing capture config into an internal field set.

    - ``True``  -> returns *safe_defaults*
    - ``False`` -> returns ``None`` (nothing captured)
    - ``list[str]`` -> returns ``frozenset(list)``
    """
    if capture is True:
        return safe_defaults
    if capture is False:
        return None
    return frozenset(capture)


# ---------------------------------------------------------------------------
# Request attribute extraction
# ---------------------------------------------------------------------------


_JSON_FIELDS = frozenset({
    "input", "tools", "reasoning", "tool_choice", "instructions",
    "include", "metadata", "response_format", "modalities", "stream_options",
})


def _extract_responses_request_attrs(
    kwargs: dict[str, Any],
    fields: frozenset[str] | None,
) -> dict[str, Any]:
    """Extract span attributes from ``create()`` keyword arguments.

    Only kwargs whose name appears in *fields* are captured.
    Returns empty dict when *fields* is ``None``.
    """
    if fields is None:
        return {}

    attrs: dict[str, Any] = {}
    for name in fields & kwargs.keys():
        value = kwargs[name]
        attr_key = RESPONSES_INPUT_ATTR_MAP.get(name)
        target_key = attr_key or f"gen_ai.request.{name}"

        # Prompt decomposition: extract sub-fields when value is a dict
        if name == "prompt" and isinstance(value, dict):
            attrs[target_key] = json.dumps(value)
            if "id" in value:
                attrs[GENAI_PROMPT_ID] = value["id"]
            if "version" in value:
                attrs[GENAI_PROMPT_VERSION] = value["version"]
            if "variables" in value:
                attrs[GENAI_PROMPT_VARIABLES] = json.dumps(value["variables"])
        elif name in _JSON_FIELDS:
            attrs[target_key] = json.dumps(value) if not isinstance(value, str) else value
        else:
            attrs[target_key] = value

    return attrs


# ---------------------------------------------------------------------------
# Response attribute extraction
# ---------------------------------------------------------------------------


def _serialize(value: Any) -> str | None:
    """Serialize a value to JSON, handling Pydantic models."""
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return json.dumps(value.model_dump())
    try:
        return json.dumps(value)
    except (TypeError, ValueError):
        return None


def _serialize_list(values: Any) -> str | None:
    """Serialize a list of values (possibly Pydantic models) to JSON."""
    if values is None:
        return None
    items = []
    for v in values:
        if hasattr(v, "model_dump"):
            items.append(v.model_dump())
        else:
            items.append(v)
    try:
        return json.dumps(items)
    except (TypeError, ValueError):
        return None


# Response field → (attribute key, serialization mode)
# Modes: "str", "float_ts", "bool", "int", "float", "json", "json_list",
#        "json_or_str" (pass strings as-is, JSON-serialize non-strings)
_RESPONSE_FIELD_MAP: dict[str, tuple[str, str]] = {
    "id": (GENAI_RESPONSE_ID, "str"),
    "object": (GENAI_RESPONSE_OBJECT, "str"),
    "model": (GENAI_RESPONSE_MODEL, "str"),
    "status": (GENAI_RESPONSE_STATUS, "str"),
    "created_at": (GENAI_RESPONSE_CREATED, "float_ts"),
    "background": (GENAI_RESPONSE_BACKGROUND, "bool"),
    "parallel_tool_calls": (GENAI_RESPONSE_PARALLEL_TOOL_CALLS, "bool"),
    "max_output_tokens": (GENAI_RESPONSE_MAX_OUTPUT_TOKENS, "int"),
    "temperature": (GENAI_RESPONSE_TEMPERATURE, "float"),
    "top_p": (GENAI_RESPONSE_TOP_P, "float"),
    "service_tier": (GENAI_RESPONSE_SERVICE_TIER, "str"),
    "output": (GENAI_OUTPUT_MESSAGES, "json_list"),
    "instructions": (GENAI_SYSTEM_INSTRUCTIONS, "json_or_str"),
    "tools": (GENAI_RESPONSE_TOOLS, "json_list"),
    "tool_choice": (GENAI_RESPONSE_TOOL_CHOICE, "json_or_str"),
    "reasoning": (GENAI_RESPONSE_REASONING, "json"),
    "text": (GENAI_OUTPUT_TYPE, "json"),
    "prompt": (GENAI_RESPONSE_PROMPT, "json"),
}


def _extract_responses_response_attrs(
    response: Any,
    fields: frozenset[str] | None,
) -> dict[str, Any]:
    """Extract span attributes from an ``openai.types.responses.Response``.

    Returns empty dict when *fields* is ``None``.
    """
    if fields is None:
        return {}

    attrs: dict[str, Any] = {}

    for field_name in fields:
        mapping = _RESPONSE_FIELD_MAP.get(field_name)
        if mapping is None:
            # Handle usage specially below
            if field_name == "usage":
                continue
            continue

        attr_key, mode = mapping
        value = getattr(response, field_name, None)
        if value is None:
            continue

        if mode == "str":
            attrs[attr_key] = str(value)
        elif mode == "float_ts":
            if hasattr(value, "timestamp"):
                attrs[attr_key] = value.timestamp()
            else:
                attrs[attr_key] = float(value)
        elif mode == "bool":
            attrs[attr_key] = bool(value)
        elif mode == "int":
            attrs[attr_key] = int(value)
        elif mode == "float":
            attrs[attr_key] = float(value)
        elif mode == "json":
            serialized = _serialize(value)
            if serialized is not None:
                attrs[attr_key] = serialized
        elif mode == "json_or_str":
            if isinstance(value, str):
                attrs[attr_key] = value
            else:
                serialized = _serialize(value)
                if serialized is not None:
                    attrs[attr_key] = serialized
        elif mode == "json_list":
            serialized = _serialize_list(value)
            if serialized is not None:
                attrs[attr_key] = serialized

    # Usage: full JSON + individual token fields
    if "usage" in fields:
        usage = getattr(response, "usage", None)
        if usage is not None:
            attrs[GENAI_USAGE_INPUT_TOKENS] = getattr(usage, "input_tokens", 0)
            attrs[GENAI_USAGE_OUTPUT_TOKENS] = getattr(usage, "output_tokens", 0)
            attrs[GENAI_USAGE_TOTAL_TOKENS] = getattr(usage, "total_tokens", 0)
            usage_json = _serialize(usage)
            if usage_json is not None:
                attrs[GENAI_USAGE] = usage_json

    return attrs


# ---------------------------------------------------------------------------
# TracedResponseStream
# ---------------------------------------------------------------------------


class TracedResponseStream:
    """Streaming wrapper that manages span lifecycle across iteration.

    Unlike TracedChatStream, this does not need chunk-by-chunk aggregation.
    The ``response.completed`` SSE event contains the full Response object
    with usage data, which the inner ResponseStream captures automatically.
    """

    def __init__(
        self,
        inner: Any,
        span: Any,
        context_token: Any,
        output_fields: frozenset[str] | None,
    ) -> None:
        self._inner = inner
        self._span = span
        self._context_token = context_token
        self._output_fields = output_fields
        self._chunk_count = 0
        self._completed = False
        self._finalized = False
        self._start_time = time.monotonic()
        self._first_chunk_time: float | None = None

    @property
    def completed_response(self) -> Any | None:
        """Proxy to inner stream's completed_response."""
        return getattr(self._inner, "completed_response", None)

    def __iter__(self):
        try:
            for event in self._inner:
                if self._first_chunk_time is None:
                    self._first_chunk_time = time.monotonic()
                    self._span.set_attribute(
                        BUD_INFERENCE_TTFT_MS,
                        (self._first_chunk_time - self._start_time) * 1000,
                    )
                self._chunk_count += 1
                yield event
            self._completed = True
        except GeneratorExit:
            pass
        except Exception as exc:
            _record_exception(self._span, exc)
            raise
        finally:
            self._finalize()

    def _finalize(self) -> None:
        if self._finalized:
            return
        self._finalized = True

        self._span.set_attribute(BUD_INFERENCE_CHUNKS, self._chunk_count)
        self._span.set_attribute(BUD_INFERENCE_STREAM_COMPLETED, self._completed)

        # Extract response attributes from the completed Response object
        completed_response = getattr(self._inner, "completed_response", None)
        if completed_response is not None:
            try:
                for k, v in _extract_responses_response_attrs(
                    completed_response, self._output_fields
                ).items():
                    self._span.set_attribute(k, v)
            except Exception:
                logger.debug("Failed to extract response attributes from stream", exc_info=True)

        if self._completed:
            _set_ok_status(self._span)

        self._span.end()
        if self._context_token is not None:
            try:
                from opentelemetry import context

                context.detach(self._context_token)
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def close(self) -> None:
        if hasattr(self._inner, "close"):
            self._inner.close()

    def __del__(self) -> None:
        if not self._finalized:
            logger.warning("TracedResponseStream was garbage-collected without iteration")
            self._finalize()


# ---------------------------------------------------------------------------
# Public API: track_responses()
# ---------------------------------------------------------------------------


def track_responses(
    client: BudClient,
    *,
    capture_input: FieldCapture = True,
    capture_output: FieldCapture = True,
    span_name: str = "responses",
) -> BudClient:
    """Instrument ``client.responses.create()`` with OTel spans.

    Args:
        client: The ``BudClient`` instance to instrument.
        capture_input: Controls which request kwargs are recorded.
            ``True`` = all fields, ``False`` = nothing,
            ``list[str]`` = exactly those fields.
        capture_output: Controls which response fields are recorded.
            ``True`` = all fields, ``False`` = nothing,
            ``list[str]`` = exactly those fields.
        span_name: Base span name. Streaming calls use ``"{span_name}.stream"``.

    Returns:
        The same *client* object (mutated in place).
    """
    # Step 1: Idempotency guard
    if getattr(client.responses, "_bud_tracked", False):
        return client

    # Step 2: Save original method reference
    original_create = client.responses.create

    # Step 3: Resolve field sets (once at patch time)
    input_fields = _resolve_fields(capture_input, RESPONSES_SAFE_INPUT_FIELDS)
    output_fields = _resolve_fields(capture_output, RESPONSES_SAFE_OUTPUT_FIELDS)

    # Step 4: Define wrapper
    def traced_create(**kwargs: Any) -> Any:
        if _is_noop():
            return original_create(**kwargs)

        from bud.observability import create_traced_span, get_tracer

        is_streaming = kwargs.get("stream", False)
        effective_span_name = f"{span_name}.stream" if is_streaming else span_name

        span, token = create_traced_span(effective_span_name, get_tracer("bud.inference"))

        # Always-on attributes
        span.set_attribute(GENAI_SYSTEM, "bud")
        span.set_attribute(BUD_INFERENCE_OPERATION, "responses")
        span.set_attribute(GENAI_OPERATION_NAME, "responses")
        span.set_attribute(BUD_INFERENCE_STREAM, bool(is_streaming))

        # Map previous_response_id to conversation.id
        prev_id = kwargs.get("previous_response_id")
        if prev_id is not None:
            span.set_attribute(GENAI_CONVERSATION_ID, prev_id)

        # Request attributes
        try:
            for k, v in _extract_responses_request_attrs(kwargs, input_fields).items():
                span.set_attribute(k, v)
        except Exception:
            logger.debug("Failed to extract request attributes", exc_info=True)

        # Call original
        try:
            result = original_create(**kwargs)
        except Exception as exc:
            _record_exception(span, exc)
            span.end()
            try:
                from opentelemetry import context

                context.detach(token)
            except Exception:
                pass
            raise

        # Handle response
        if is_streaming:
            return TracedResponseStream(result, span, token, output_fields)

        # Non-streaming: extract response attrs, finalize span
        try:
            for k, v in _extract_responses_response_attrs(result, output_fields).items():
                span.set_attribute(k, v)
        except Exception:
            logger.debug("Failed to extract response attributes", exc_info=True)

        _set_ok_status(span)
        span.end()
        try:
            from opentelemetry import context

            context.detach(token)
        except Exception:
            pass
        return result

    # Step 5: Monkey-patch
    client.responses.create = traced_create  # type: ignore[assignment]
    client.responses._bud_tracked = True  # type: ignore[attr-defined]
    return client
