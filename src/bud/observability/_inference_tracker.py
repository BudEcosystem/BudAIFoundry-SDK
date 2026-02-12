"""Inference-level tracing for chat completions.

Instruments ``client.chat.completions.create()`` with OTel spans for both
streaming and non-streaming calls.  Records request parameters, response
metadata, token usage, and time-to-first-token as span attributes following
the OpenTelemetry GenAI Semantic Conventions.

Usage::

    from bud import BudClient
    from bud.observability import track_chat_completions

    client = BudClient(api_key="...")
    track_chat_completions(client)

    response = client.chat.completions.create(model="gpt-4", messages=[...])
"""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any

from bud.observability._genai_attributes import (
    BUD_INFERENCE_CHUNKS,
    BUD_INFERENCE_OPERATION,
    BUD_INFERENCE_RESPONSE_CHOICES,
    BUD_INFERENCE_STREAM,
    BUD_INFERENCE_STREAM_COMPLETED,
    BUD_INFERENCE_TTFT_MS,
    CHAT_INPUT_ATTR_MAP,
    CHAT_SAFE_INPUT_FIELDS,
    CHAT_SAFE_OUTPUT_FIELDS,
    GENAI_RESPONSE_CREATED,
    GENAI_RESPONSE_ID,
    GENAI_RESPONSE_MODEL,
    GENAI_RESPONSE_OBJECT,
    GENAI_RESPONSE_SYSTEM_FINGERPRINT,
    GENAI_SYSTEM,
    GENAI_USAGE_INPUT_TOKENS,
    GENAI_USAGE_OUTPUT_TOKENS,
    GENAI_USAGE_TOTAL_TOKENS,
)
from bud.observability._track import _is_noop, _record_exception, _set_ok_status

if TYPE_CHECKING:
    from bud.client import BudClient
    from bud.models.inference import ChatCompletion, ChatCompletionChunk

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

    - ``True`` → returns *safe_defaults* (no PII)
    - ``False`` → returns ``None`` (nothing captured)
    - ``list[str]`` → returns ``frozenset(list)``
    """
    if capture is True:
        return safe_defaults
    if capture is False:
        return None
    return frozenset(capture)


# ---------------------------------------------------------------------------
# Request attribute extraction
# ---------------------------------------------------------------------------


def _extract_chat_request_attrs(
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
        attr_key = CHAT_INPUT_ATTR_MAP.get(name)

        if name in ("messages", "tools"):
            target_key = attr_key or f"bud.inference.request.{name}"
            attrs[target_key] = json.dumps(value)
        elif name == "tool_choice":
            target_key = attr_key or f"bud.inference.request.{name}"
            attrs[target_key] = json.dumps(value) if not isinstance(value, str) else value
        elif name == "stop" and isinstance(value, list):
            target_key = attr_key or f"bud.inference.request.{name}"
            attrs[target_key] = json.dumps(value)
        else:
            target_key = attr_key or f"bud.inference.request.{name}"
            attrs[target_key] = value

    return attrs


# ---------------------------------------------------------------------------
# Response attribute extraction
# ---------------------------------------------------------------------------


def _extract_chat_response_attrs(
    response: ChatCompletion,
    fields: frozenset[str] | None,
) -> dict[str, Any]:
    """Extract span attributes from a ``ChatCompletion`` response.

    Returns empty dict when *fields* is ``None``.
    """
    if fields is None:
        return {}

    attrs: dict[str, Any] = {}

    if "id" in fields:
        attrs[GENAI_RESPONSE_ID] = response.id

    if "model" in fields:
        attrs[GENAI_RESPONSE_MODEL] = response.model

    if "created" in fields:
        attrs[GENAI_RESPONSE_CREATED] = response.created

    if "system_fingerprint" in fields and response.system_fingerprint is not None:
        attrs[GENAI_RESPONSE_SYSTEM_FINGERPRINT] = response.system_fingerprint

    if "object" in fields:
        attrs[GENAI_RESPONSE_OBJECT] = response.object

    if "usage" in fields and response.usage is not None:
        attrs[GENAI_USAGE_INPUT_TOKENS] = response.usage.prompt_tokens
        attrs[GENAI_USAGE_OUTPUT_TOKENS] = response.usage.completion_tokens
        attrs[GENAI_USAGE_TOTAL_TOKENS] = response.usage.total_tokens

    if "choices" in fields and response.choices:
        choices_data = []
        for c in response.choices:
            tc = c.message.tool_calls
            # Serialize tool_calls list — items may be dicts or objects
            tc_serializable = None
            if tc:
                tc_serializable = []
                for item in tc:
                    if isinstance(item, dict):
                        tc_serializable.append(item)
                    else:
                        tc_serializable.append(  # type: ignore[unreachable]
                            json.loads(item.model_dump_json())
                            if hasattr(item, "model_dump_json")
                            else item
                        )
            choices_data.append({
                "index": c.index if hasattr(c, "index") else 0,
                "finish_reason": c.finish_reason,
                "message": {
                    "role": getattr(c.message, "role", None),
                    "content": c.message.content,
                    "tool_calls": tc_serializable,
                },
            })
        attrs[BUD_INFERENCE_RESPONSE_CHOICES] = json.dumps(choices_data)

    return attrs


# ---------------------------------------------------------------------------
# Stream aggregation
# ---------------------------------------------------------------------------


def _aggregate_stream_response(
    chunks: list[ChatCompletionChunk],
    fields: frozenset[str] | None,
) -> dict[str, Any]:
    """Aggregate accumulated stream chunks into span attributes.

    Returns empty dict when *fields* is ``None`` or *chunks* is empty.
    """
    if fields is None or not chunks:
        return {}

    attrs: dict[str, Any] = {}

    if "id" in fields:
        for chunk in chunks:
            if chunk.id:
                attrs[GENAI_RESPONSE_ID] = chunk.id
                break

    if "model" in fields:
        for chunk in chunks:
            if chunk.model:
                attrs[GENAI_RESPONSE_MODEL] = chunk.model
                break

    if "system_fingerprint" in fields:
        for chunk in chunks:
            if chunk.system_fingerprint is not None:
                attrs[GENAI_RESPONSE_SYSTEM_FINGERPRINT] = chunk.system_fingerprint
                break

    if "usage" in fields:
        for chunk in reversed(chunks):
            usage = getattr(chunk, "usage", None)
            if usage is not None:
                attrs[GENAI_USAGE_INPUT_TOKENS] = getattr(usage, "prompt_tokens", 0)
                attrs[GENAI_USAGE_OUTPUT_TOKENS] = getattr(usage, "completion_tokens", 0)
                attrs[GENAI_USAGE_TOTAL_TOKENS] = getattr(usage, "total_tokens", 0)
                break

    if "choices" in fields:
        # Reconstruct choices from stream deltas
        finish_reason = None
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_calls_parts: list[Any] = []

        for chunk in chunks:
            if chunk.choices:
                delta = chunk.choices[0].delta
                if delta.content is not None:
                    content_parts.append(delta.content)
                if getattr(delta, "reasoning_content", None) is not None:
                    reasoning_parts.append(delta.reasoning_content)  # type: ignore[arg-type]
                tc = getattr(delta, "tool_calls", None)
                if tc:
                    tool_calls_parts.extend(tc)
                reason = chunk.choices[0].finish_reason
                if reason is not None:
                    finish_reason = reason

        content = "".join(content_parts)
        if reasoning_parts:
            reasoning = "".join(reasoning_parts)
            content = f"{content}\n[Reasoning: {reasoning}]" if content else f"[Reasoning: {reasoning}]"

        # Serialize tool_calls — items may be dicts or objects
        tc_serializable = None
        if tool_calls_parts:
            tc_serializable = []
            for item in tool_calls_parts:
                if isinstance(item, dict):
                    tc_serializable.append(item)
                else:
                    tc_serializable.append(
                        json.loads(item.model_dump_json())
                        if hasattr(item, "model_dump_json")
                        else item
                    )

        choice_data: dict[str, Any] = {
            "index": 0,
            "finish_reason": finish_reason,
            "message": {
                "content": content or None,
                "tool_calls": tc_serializable,
            },
        }
        attrs[BUD_INFERENCE_RESPONSE_CHOICES] = json.dumps([choice_data])

    return attrs


# ---------------------------------------------------------------------------
# TracedChatStream
# ---------------------------------------------------------------------------


class TracedChatStream:
    """Streaming wrapper that manages span lifecycle across iteration.

    Implements ``__iter__``, ``__enter__``/``__exit__``, and ``close()``
    so it can be used as a drop-in replacement for the original stream.
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
        self._accumulated: list[Any] = []
        self._completed = False
        self._finalized = False
        self._start_time = time.monotonic()
        self._first_chunk_time: float | None = None

    def __iter__(self):
        try:
            for chunk in self._inner:
                if self._first_chunk_time is None:
                    self._first_chunk_time = time.monotonic()
                    self._span.set_attribute(
                        BUD_INFERENCE_TTFT_MS,
                        (self._first_chunk_time - self._start_time) * 1000,
                    )
                self._chunk_count += 1
                self._accumulated.append(chunk)
                yield chunk
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

        if self._accumulated:
            try:
                for k, v in _aggregate_stream_response(
                    self._accumulated, self._output_fields
                ).items():
                    self._span.set_attribute(k, v)
            except Exception:
                logger.debug("Failed to aggregate stream response", exc_info=True)

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
            logger.warning("TracedChatStream was garbage-collected without iteration")
            self._finalize()


# ---------------------------------------------------------------------------
# Public API: track_chat_completions()
# ---------------------------------------------------------------------------


def track_chat_completions(
    client: BudClient,
    *,
    capture_input: FieldCapture = True,
    capture_output: FieldCapture = True,
    span_name: str = "chat",
) -> BudClient:
    """Instrument ``client.chat.completions.create()`` with OTel spans.

    Args:
        client: The ``BudClient`` instance to instrument.
        capture_input: Controls which request kwargs are recorded.
            ``True`` = all fields (messages, tools, user, etc.),
            ``False`` = nothing, ``list[str]`` = exactly those fields.
        capture_output: Controls which response fields are recorded.
            ``True`` = all root-level ChatCompletion keys (id, object, model,
            created, choices, usage, system_fingerprint),
            ``False`` = nothing, ``list[str]`` = exactly those fields.
        span_name: Base span name. Streaming calls use ``"{span_name}.stream"``.

    Returns:
        The same *client* object (mutated in place).
    """
    # Step 1: Idempotency guard
    if getattr(client.chat.completions, "_bud_tracked", False):
        return client

    # Step 2: Save original method reference
    original_create = client.chat.completions.create

    # Step 3: Resolve field sets (once at patch time)
    input_fields = _resolve_fields(capture_input, CHAT_SAFE_INPUT_FIELDS)
    output_fields = _resolve_fields(capture_output, CHAT_SAFE_OUTPUT_FIELDS)

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
        span.set_attribute(BUD_INFERENCE_OPERATION, "chat")
        span.set_attribute(BUD_INFERENCE_STREAM, bool(is_streaming))

        # Request attributes
        try:
            for k, v in _extract_chat_request_attrs(kwargs, input_fields).items():
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
            return TracedChatStream(result, span, token, output_fields)

        # Non-streaming: extract response attrs, finalize span
        try:
            for k, v in _extract_chat_response_attrs(result, output_fields).items():
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
    client.chat.completions.create = traced_create  # type: ignore[method-assign]
    client.chat.completions._bud_tracked = True  # type: ignore[attr-defined]
    return client
