"""Tests for Responses API resource."""

from __future__ import annotations

import json
from typing import Any

import pytest
import respx
from httpx import Response

from bud.client import BudClient


@pytest.fixture
def sample_responses_response() -> dict[str, Any]:
    """Sample Responses API response matching openai.types.responses.Response."""
    return {
        "id": "resp_abc123",
        "object": "response",
        "created_at": 1700000000,
        "model": "gpt-4.1",
        "status": "completed",
        "output": [
            {
                "type": "message",
                "id": "msg_001",
                "status": "completed",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": "The capital of France is Paris.",
                        "annotations": [],
                    }
                ],
            }
        ],
        "usage": {
            "input_tokens": 12,
            "output_tokens": 8,
            "total_tokens": 20,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 0},
        },
        "text": {"format": {"type": "text"}},
        "parallel_tool_calls": True,
        "tool_choice": "auto",
        "tools": [],
        "top_p": 1.0,
        "temperature": 1.0,
        "max_output_tokens": None,
        "truncation": "disabled",
        "metadata": {},
    }


# Non-streaming tests


@respx.mock
def test_create_response_non_streaming(
    client: BudClient,
    base_url: str,
    sample_responses_response: dict[str, Any],
) -> None:
    """Test creating a non-streaming response."""
    respx.post(f"{base_url}/v1/responses").mock(
        return_value=Response(200, json=sample_responses_response)
    )

    result = client.responses.create(
        model="gpt-4.1",
        input="What is the capital of France?",
    )

    assert result.id == "resp_abc123"
    assert result.model == "gpt-4.1"
    assert result.status == "completed"
    assert result.output_text == "The capital of France is Paris."


@respx.mock
def test_create_response_with_all_params(
    client: BudClient,
    base_url: str,
    sample_responses_response: dict[str, Any],
) -> None:
    """Test that all optional params are included in the request payload."""
    route = respx.post(f"{base_url}/v1/responses").mock(
        return_value=Response(200, json=sample_responses_response)
    )

    client.responses.create(
        model="gpt-4.1",
        input="Hello",
        instructions="Be helpful",
        temperature=0.7,
        top_p=0.9,
        max_output_tokens=100,
        user="user-123",
        previous_response_id="resp_prev",
        store=True,
        service_tier="default",
    )

    request = route.calls.last.request
    payload = json.loads(request.content)
    assert payload["model"] == "gpt-4.1"
    assert payload["input"] == "Hello"
    assert payload["instructions"] == "Be helpful"
    assert payload["temperature"] == 0.7
    assert payload["top_p"] == 0.9
    assert payload["max_output_tokens"] == 100
    assert payload["user"] == "user-123"
    assert payload["previous_response_id"] == "resp_prev"
    assert payload["store"] is True
    assert payload["service_tier"] == "default"


def test_create_response_requires_model_or_prompt(client: BudClient) -> None:
    """Test that ValueError is raised if neither model nor prompt is provided."""
    with pytest.raises(ValueError, match="At least one of 'model' or 'prompt'"):
        client.responses.create(input="Hello")


@respx.mock
def test_create_response_with_prompt_param(
    client: BudClient,
    base_url: str,
    sample_responses_response: dict[str, Any],
) -> None:
    """Test that prompt param works without model."""
    route = respx.post(f"{base_url}/v1/responses").mock(
        return_value=Response(200, json=sample_responses_response)
    )

    client.responses.create(
        prompt={"id": "prompt_abc"},
        input="Hello",
    )

    request = route.calls.last.request
    payload = json.loads(request.content)
    assert payload["prompt"] == {"id": "prompt_abc"}
    assert "model" not in payload


# Error tests


@respx.mock
def test_create_response_401(client: BudClient, base_url: str) -> None:
    """Test 401 error mapping."""
    from bud.exceptions import AuthenticationError

    respx.post(f"{base_url}/v1/responses").mock(
        return_value=Response(401, json={"error": "Invalid API key"})
    )
    with pytest.raises(AuthenticationError):
        client.responses.create(model="gpt-4.1", input="Hello")


@respx.mock
def test_create_response_404(client: BudClient, base_url: str) -> None:
    """Test 404 error mapping."""
    from bud.exceptions import NotFoundError

    respx.post(f"{base_url}/v1/responses").mock(
        return_value=Response(404, json={"error": "Model not found"})
    )
    with pytest.raises(NotFoundError):
        client.responses.create(model="nonexistent", input="Hello")


@respx.mock
def test_create_response_422(client: BudClient, base_url: str) -> None:
    """Test 422 error mapping."""
    from bud.exceptions import ValidationError

    respx.post(f"{base_url}/v1/responses").mock(
        return_value=Response(422, json={"message": "Invalid params", "errors": []})
    )
    with pytest.raises(ValidationError):
        client.responses.create(model="gpt-4.1", input="Hello")


@respx.mock
def test_create_response_429(client: BudClient, base_url: str) -> None:
    """Test 429 error mapping."""
    from bud.exceptions import RateLimitError

    respx.post(f"{base_url}/v1/responses").mock(
        return_value=Response(429, json={"error": "Rate limited"})
    )
    with pytest.raises(RateLimitError):
        client.responses.create(model="gpt-4.1", input="Hello")


@respx.mock
def test_create_response_500(client: BudClient, base_url: str) -> None:
    """Test 500 error mapping."""
    from bud.exceptions import BudError

    respx.post(f"{base_url}/v1/responses").mock(
        return_value=Response(500, json={"error": "Internal error"})
    )
    with pytest.raises(BudError):
        client.responses.create(model="gpt-4.1", input="Hello")
