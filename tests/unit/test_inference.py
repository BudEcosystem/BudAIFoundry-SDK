"""Tests for OpenAI-compatible inference API."""

from __future__ import annotations

import json
from typing import Any

import pytest
import respx
from httpx import Response

from bud._streaming import SSEParser
from bud.client import BudClient
from bud.models.inference import (
    ChatCompletion,
    ChatCompletionChunk,
    EmbeddingResponse,
    Model,
    ModelList,
)


@pytest.fixture
def sample_chat_completion() -> dict[str, Any]:
    """Sample chat completion response."""
    return {
        "id": "chatcmpl-abc123",
        "object": "chat.completion",
        "created": 1700000000,
        "model": "gpt-4",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Hello! How can I help you today?",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 8,
            "total_tokens": 18,
        },
    }


@pytest.fixture
def sample_embedding_response() -> dict[str, Any]:
    """Sample embedding response."""
    return {
        "object": "list",
        "data": [
            {
                "index": 0,
                "embedding": [0.1, 0.2, 0.3, 0.4, 0.5],
                "object": "embedding",
            }
        ],
        "model": "text-embedding-3-small",
        "usage": {
            "prompt_tokens": 5,
            "total_tokens": 5,
        },
    }


@pytest.fixture
def sample_model() -> dict[str, Any]:
    """Sample model response."""
    return {
        "id": "gpt-4",
        "object": "model",
        "created": 1700000000,
        "owned_by": "openai",
    }


@pytest.fixture
def sample_model_list() -> dict[str, Any]:
    """Sample model list response."""
    return {
        "object": "list",
        "data": [
            {
                "id": "gpt-4",
                "object": "model",
                "created": 1700000000,
                "owned_by": "openai",
            },
            {
                "id": "gpt-3.5-turbo",
                "object": "model",
                "created": 1699000000,
                "owned_by": "openai",
            },
        ],
    }


# Chat Completion Tests


@respx.mock
def test_create_chat_completion(
    client: BudClient,
    base_url: str,
    sample_chat_completion: dict[str, Any],
) -> None:
    """Test creating a chat completion."""
    respx.post(f"{base_url}/v1/chat/completions").mock(
        return_value=Response(200, json=sample_chat_completion)
    )

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello!"}],
    )

    assert isinstance(response, ChatCompletion)
    assert response.id == "chatcmpl-abc123"
    assert response.model == "gpt-4"
    assert len(response.choices) == 1
    assert response.choices[0].message.content == "Hello! How can I help you today?"
    assert response.usage is not None
    assert response.usage.total_tokens == 18


@respx.mock
def test_create_chat_completion_with_options(
    client: BudClient,
    base_url: str,
    sample_chat_completion: dict[str, Any],
) -> None:
    """Test creating a chat completion with all options."""
    route = respx.post(f"{base_url}/v1/chat/completions").mock(
        return_value=Response(200, json=sample_chat_completion)
    )

    client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello!"}],
        temperature=0.7,
        top_p=0.9,
        max_tokens=100,
        stop=["STOP"],
        presence_penalty=0.1,
        frequency_penalty=0.1,
        user="user-123",
    )

    # Verify request payload
    request = route.calls.last.request
    payload = json.loads(request.content)
    assert payload["temperature"] == 0.7
    assert payload["top_p"] == 0.9
    assert payload["max_tokens"] == 100
    assert payload["stop"] == ["STOP"]
    assert payload["presence_penalty"] == 0.1
    assert payload["frequency_penalty"] == 0.1
    assert payload["user"] == "user-123"


# Embedding Tests


@respx.mock
def test_create_embedding(
    client: BudClient,
    base_url: str,
    sample_embedding_response: dict[str, Any],
) -> None:
    """Test creating embeddings."""
    respx.post(f"{base_url}/v1/embeddings").mock(
        return_value=Response(200, json=sample_embedding_response)
    )

    response = client.embeddings.create(
        model="text-embedding-3-small",
        input="Hello, world!",
    )

    assert isinstance(response, EmbeddingResponse)
    assert response.model == "text-embedding-3-small"
    assert len(response.data) == 1
    assert len(response.data[0].embedding) == 5
    assert response.usage.total_tokens == 5


@respx.mock
def test_create_embedding_batch(
    client: BudClient,
    base_url: str,
) -> None:
    """Test creating embeddings for multiple inputs."""
    batch_response = {
        "object": "list",
        "data": [
            {"index": 0, "embedding": [0.1, 0.2], "object": "embedding"},
            {"index": 1, "embedding": [0.3, 0.4], "object": "embedding"},
        ],
        "model": "text-embedding-3-small",
        "usage": {"prompt_tokens": 10, "total_tokens": 10},
    }

    respx.post(f"{base_url}/v1/embeddings").mock(
        return_value=Response(200, json=batch_response)
    )

    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=["Hello", "World"],
    )

    assert len(response.data) == 2
    assert response.data[0].index == 0
    assert response.data[1].index == 1


# Model Tests


@respx.mock
def test_list_models(
    client: BudClient,
    base_url: str,
    sample_model_list: dict[str, Any],
) -> None:
    """Test listing models."""
    respx.get(f"{base_url}/v1/models").mock(
        return_value=Response(200, json=sample_model_list)
    )

    response = client.models.list()

    assert isinstance(response, ModelList)
    assert len(response.data) == 2
    assert response.data[0].id == "gpt-4"
    assert response.data[1].id == "gpt-3.5-turbo"


@respx.mock
def test_retrieve_model(
    client: BudClient,
    base_url: str,
    sample_model: dict[str, Any],
) -> None:
    """Test retrieving a specific model."""
    respx.get(f"{base_url}/v1/models/gpt-4").mock(
        return_value=Response(200, json=sample_model)
    )

    model = client.models.retrieve("gpt-4")

    assert isinstance(model, Model)
    assert model.id == "gpt-4"
    assert model.owned_by == "openai"


# SSE Parser Tests


def test_sse_parser_basic() -> None:
    """Test basic SSE parsing."""
    parser = SSEParser()

    # Feed partial event
    assert parser.feed("data: hello") is None

    # Empty line completes the event
    event = parser.feed("")
    assert event is not None
    assert event["data"] == "hello"


def test_sse_parser_multiline_data() -> None:
    """Test SSE parser with multiline data."""
    parser = SSEParser()

    parser.feed("data: line1")
    parser.feed("data: line2")
    event = parser.feed("")

    assert event is not None
    assert event["data"] == "line1\nline2"


def test_sse_parser_with_event_type() -> None:
    """Test SSE parser with event type."""
    parser = SSEParser()

    parser.feed("event: message")
    parser.feed("data: test")
    event = parser.feed("")

    assert event is not None
    assert event["event"] == "message"
    assert event["data"] == "test"


def test_sse_parser_comment_ignored() -> None:
    """Test that SSE comments are ignored."""
    parser = SSEParser()

    assert parser.feed(": this is a comment") is None
    parser.feed("data: test")
    event = parser.feed("")

    assert event["data"] == "test"


def test_sse_parser_max_line_length() -> None:
    """Test SSE parser enforces max line length."""
    parser = SSEParser()

    long_line = "x" * (SSEParser.MAX_LINE_LENGTH + 1)
    with pytest.raises(ValueError, match="exceeds maximum length"):
        parser.feed(long_line)


def test_sse_parser_max_events() -> None:
    """Test SSE parser enforces max events."""
    parser = SSEParser()
    parser._event_count = SSEParser.MAX_EVENTS

    with pytest.raises(ValueError, match="exceeded maximum"):
        parser.feed("data: test")


# Pydantic Model Tests


def test_chat_completion_model(sample_chat_completion: dict[str, Any]) -> None:
    """Test ChatCompletion model validation."""
    completion = ChatCompletion.model_validate(sample_chat_completion)

    assert completion.id == "chatcmpl-abc123"
    assert completion.object == "chat.completion"
    assert completion.created == 1700000000
    assert completion.model == "gpt-4"
    assert len(completion.choices) == 1
    assert completion.choices[0].message.role == "assistant"
    assert completion.usage is not None
    assert completion.usage.prompt_tokens == 10


def test_chat_completion_chunk_model() -> None:
    """Test ChatCompletionChunk model validation."""
    chunk_data = {
        "id": "chatcmpl-abc123",
        "object": "chat.completion.chunk",
        "created": 1700000000,
        "model": "gpt-4",
        "choices": [
            {
                "index": 0,
                "delta": {"content": "Hello"},
                "finish_reason": None,
            }
        ],
    }

    chunk = ChatCompletionChunk.model_validate(chunk_data)

    assert chunk.id == "chatcmpl-abc123"
    assert chunk.object == "chat.completion.chunk"
    assert chunk.choices[0].delta.content == "Hello"


def test_embedding_response_model(sample_embedding_response: dict[str, Any]) -> None:
    """Test EmbeddingResponse model validation."""
    response = EmbeddingResponse.model_validate(sample_embedding_response)

    assert response.object == "list"
    assert len(response.data) == 1
    assert response.data[0].index == 0
    assert len(response.data[0].embedding) == 5
    assert response.model == "text-embedding-3-small"
    assert response.usage.prompt_tokens == 5


def test_model_with_extra_fields() -> None:
    """Test that models allow extra fields for forward compatibility."""
    model_data = {
        "id": "gpt-4",
        "object": "model",
        "created": 1700000000,
        "owned_by": "openai",
        "future_field": "some_value",  # Extra field
    }

    model = Model.model_validate(model_data)
    assert model.id == "gpt-4"
    # Extra field should be accessible
    assert hasattr(model, "future_field") or "future_field" in model.model_extra


# Streaming Tests


@respx.mock
def test_create_chat_completion_streaming(
    client: BudClient,
    base_url: str,
) -> None:
    """Test creating a chat completion with streaming."""
    sse_data = (
        'data: {"id":"1","object":"chat.completion.chunk","created":1,"model":"gpt-4","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}\n\n'
        'data: {"id":"1","object":"chat.completion.chunk","created":1,"model":"gpt-4","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}\n\n'
        'data: {"id":"1","object":"chat.completion.chunk","created":1,"model":"gpt-4","choices":[{"index":0,"delta":{"content":" there"},"finish_reason":null}]}\n\n'
        'data: {"id":"1","object":"chat.completion.chunk","created":1,"model":"gpt-4","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\n'
        "data: [DONE]\n\n"
    )

    respx.post(f"{base_url}/v1/chat/completions").mock(
        return_value=Response(
            200,
            content=sse_data.encode(),
            headers={"Content-Type": "text/event-stream"},
        )
    )

    stream = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello!"}],
        stream=True,
    )

    chunks = list(stream)
    assert len(chunks) == 4
    assert isinstance(chunks[0], ChatCompletionChunk)
    assert chunks[0].choices[0].delta.role == "assistant"
    assert chunks[1].choices[0].delta.content == "Hello"
    assert chunks[2].choices[0].delta.content == " there"
    assert chunks[3].choices[0].finish_reason == "stop"


# Validation Tests


def test_chat_completion_message_limit(client: BudClient) -> None:
    """Test that message count is validated."""
    # Create more than 1000 messages
    messages = [{"role": "user", "content": f"Message {i}"} for i in range(1001)]

    with pytest.raises(ValueError, match="exceeds maximum of 1000 messages"):
        client.chat.completions.create(
            model="gpt-4",
            messages=messages,
        )


# Extended Embedding Tests


@respx.mock
def test_create_embedding_with_extended_params(
    client: BudClient,
    base_url: str,
) -> None:
    """Test creating embeddings with extended parameters."""
    extended_response = {
        "object": "list",
        "data": [
            {
                "index": 0,
                "embedding": [0.1, 0.2, 0.3],
                "object": "embedding",
                "text": "Hello, world!",
            }
        ],
        "model": "BAAI/bge-small-en-v1.5",
        "usage": {"prompt_tokens": 5, "total_tokens": 5},
    }

    route = respx.post(f"{base_url}/v1/embeddings").mock(
        return_value=Response(200, json=extended_response)
    )

    response = client.embeddings.create(
        model="BAAI/bge-small-en-v1.5",
        input="Hello, world!",
        modality="text",
        priority="high",
        include_input=True,
        dimensions=512,
    )

    # Verify request payload includes extended params
    request = route.calls.last.request
    payload = json.loads(request.content)
    assert payload["modality"] == "text"
    assert payload["priority"] == "high"
    assert payload["include_input"] is True
    assert payload["dimensions"] == 512

    # Verify response includes text field
    assert response.data[0].text == "Hello, world!"


@respx.mock
def test_create_embedding_with_chunking(
    client: BudClient,
    base_url: str,
) -> None:
    """Test creating embeddings with chunking configuration."""
    chunked_response = {
        "object": "list",
        "data": [
            {
                "index": 0,
                "embedding": [0.1, 0.2],
                "object": "embedding",
                "chunk_text": "First chunk",
            },
            {
                "index": 1,
                "embedding": [0.3, 0.4],
                "object": "embedding",
                "chunk_text": "Second chunk",
            },
        ],
        "model": "BAAI/bge-small-en-v1.5",
        "usage": {"prompt_tokens": 10, "total_tokens": 10},
    }

    route = respx.post(f"{base_url}/v1/embeddings").mock(
        return_value=Response(200, json=chunked_response)
    )

    chunking_config = {
        "strategy": "sentence",
        "chunk_size": 512,
        "overlap": 50,
    }

    response = client.embeddings.create(
        model="BAAI/bge-small-en-v1.5",
        input="Long text to be chunked into multiple parts.",
        chunking=chunking_config,
    )

    # Verify chunking config in request
    request = route.calls.last.request
    payload = json.loads(request.content)
    assert payload["chunking"] == chunking_config

    # Verify chunk_text in response
    assert len(response.data) == 2
    assert response.data[0].chunk_text == "First chunk"
    assert response.data[1].chunk_text == "Second chunk"


@respx.mock
def test_create_embedding_with_cache_options(
    client: BudClient,
    base_url: str,
    sample_embedding_response: dict[str, Any],
) -> None:
    """Test creating embeddings with cache options."""
    route = respx.post(f"{base_url}/v1/embeddings").mock(
        return_value=Response(200, json=sample_embedding_response)
    )

    client.embeddings.create(
        model="BAAI/bge-small-en-v1.5",
        input="Hello, world!",
        cache_options={"enabled": "on", "max_age_s": 3600},
    )

    # Verify cache options in request with special key
    request = route.calls.last.request
    payload = json.loads(request.content)
    assert payload["tensorzero::cache_options"] == {"enabled": "on", "max_age_s": 3600}


# Classification Tests


@pytest.fixture
def sample_classify_response() -> dict[str, Any]:
    """Sample classification response."""
    return {
        "object": "classify",
        "data": [
            [
                {"label": "positive", "score": 0.85},
                {"label": "neutral", "score": 0.10},
                {"label": "negative", "score": 0.05},
            ]
        ],
        "model": "ProsusAI/finbert",
        "usage": {"prompt_tokens": 15, "total_tokens": 15},
        "id": "infinity-abc123",
        "created": 1699000000,
    }


@respx.mock
def test_create_classification(
    client: BudClient,
    base_url: str,
    sample_classify_response: dict[str, Any],
) -> None:
    """Test creating classifications."""
    from bud.models.inference import ClassifyResponse

    respx.post(f"{base_url}/v1/classify").mock(
        return_value=Response(200, json=sample_classify_response)
    )

    response = client.classifications.create(
        model="ProsusAI/finbert",
        input=["The stock market is performing well today"],
    )

    assert isinstance(response, ClassifyResponse)
    assert response.object == "classify"
    assert response.model == "ProsusAI/finbert"
    assert len(response.data) == 1
    assert len(response.data[0]) == 3
    assert response.data[0][0].label == "positive"
    assert response.data[0][0].score == 0.85
    assert response.usage.total_tokens == 15


@respx.mock
def test_create_classification_batch(
    client: BudClient,
    base_url: str,
) -> None:
    """Test creating classifications for multiple inputs."""
    batch_response = {
        "object": "classify",
        "data": [
            [
                {"label": "positive", "score": 0.9},
                {"label": "negative", "score": 0.1},
            ],
            [
                {"label": "negative", "score": 0.8},
                {"label": "positive", "score": 0.2},
            ],
        ],
        "model": "ProsusAI/finbert",
        "usage": {"prompt_tokens": 20, "total_tokens": 20},
    }

    respx.post(f"{base_url}/v1/classify").mock(
        return_value=Response(200, json=batch_response)
    )

    response = client.classifications.create(
        model="ProsusAI/finbert",
        input=["Good news!", "Bad news!"],
    )

    assert len(response.data) == 2
    assert response.data[0][0].label == "positive"
    assert response.data[1][0].label == "negative"


@respx.mock
def test_create_classification_with_options(
    client: BudClient,
    base_url: str,
    sample_classify_response: dict[str, Any],
) -> None:
    """Test creating classifications with all options."""
    route = respx.post(f"{base_url}/v1/classify").mock(
        return_value=Response(200, json=sample_classify_response)
    )

    client.classifications.create(
        model="ProsusAI/finbert",
        input=["Test input"],
        raw_scores=True,
        priority="high",
    )

    # Verify request payload
    request = route.calls.last.request
    payload = json.loads(request.content)
    assert payload["model"] == "ProsusAI/finbert"
    assert payload["input"] == ["Test input"]
    assert payload["raw_scores"] is True
    assert payload["priority"] == "high"


def test_classify_response_model(sample_classify_response: dict[str, Any]) -> None:
    """Test ClassifyResponse model validation."""
    from bud.models.inference import ClassifyResponse

    response = ClassifyResponse.model_validate(sample_classify_response)

    assert response.object == "classify"
    assert len(response.data) == 1
    assert response.data[0][0].label == "positive"
    assert response.data[0][0].score == 0.85
    assert response.model == "ProsusAI/finbert"
    assert response.usage.prompt_tokens == 15
    assert response.id == "infinity-abc123"
    assert response.created == 1699000000
