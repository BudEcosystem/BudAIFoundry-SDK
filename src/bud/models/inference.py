"""Pydantic models for OpenAI-compatible inference API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import ConfigDict, Field

from bud.models.common import BudModel


class ChatMessage(BudModel):
    """A chat message in a conversation."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = Field(default=None, max_length=1_000_000)
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


class Usage(BudModel):
    """Token usage statistics."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionChoice(BudModel):
    """A single choice in a chat completion response."""

    index: int
    message: ChatMessage
    finish_reason: Literal["stop", "length", "tool_calls", "content_filter"] | None = None


class ChatCompletion(BudModel):
    """Response from a chat completion request."""

    model_config = ConfigDict(extra="allow")

    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: Usage | None = None
    system_fingerprint: str | None = None


class ChatCompletionDelta(BudModel):
    """Delta content in a streaming chunk."""

    role: Literal["system", "user", "assistant", "tool"] | None = None
    content: str | None = None
    reasoning_content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


class ChatCompletionChunkChoice(BudModel):
    """A single choice in a streaming chat completion chunk."""

    index: int
    delta: ChatCompletionDelta
    finish_reason: Literal["stop", "length", "tool_calls", "content_filter"] | None = None


class ChatCompletionChunk(BudModel):
    """A streaming chunk from a chat completion request."""

    model_config = ConfigDict(extra="allow")

    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int
    model: str
    choices: list[ChatCompletionChunkChoice]
    system_fingerprint: str | None = None


class EmbeddingData(BudModel):
    """A single embedding result."""

    index: int
    embedding: list[float]
    object: Literal["embedding"] = "embedding"
    text: str | None = None  # Original text (if include_input=True)
    chunk_text: str | None = None  # Chunk text (if chunking enabled)


class EmbeddingUsage(BudModel):
    """Token usage for embeddings."""

    prompt_tokens: int
    total_tokens: int


class EmbeddingResponse(BudModel):
    """Response from an embedding request."""

    model_config = ConfigDict(extra="allow")

    object: Literal["list"] = "list"
    data: list[EmbeddingData]
    model: str
    usage: EmbeddingUsage


class Model(BudModel):
    """Information about an available model."""

    model_config = ConfigDict(extra="allow")

    id: str
    object: Literal["model"] = "model"
    created: int
    owned_by: str


class ModelList(BudModel):
    """List of available models."""

    object: Literal["list"] = "list"
    data: list[Model]


class ClassifyLabelScore(BudModel):
    """A single classification label with its score."""

    label: str
    score: float


class ClassifyUsage(BudModel):
    """Token usage for classification."""

    prompt_tokens: int
    total_tokens: int


class ClassifyResponse(BudModel):
    """Response from a classification request."""

    model_config = ConfigDict(extra="allow")

    object: Literal["classify"] = "classify"
    data: list[list[ClassifyLabelScore]]
    model: str
    usage: ClassifyUsage
    id: str | None = None
    created: int | None = None
