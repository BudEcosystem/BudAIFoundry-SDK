"""Tests for A2A (Agent-to-Agent) protocol resource."""

from __future__ import annotations

import json
from typing import Any

import pytest
import respx
from httpx import Response

from bud._jsonrpc import build_request, unwrap_response
from bud.client import BudClient
from bud.exceptions import A2AError
from bud.models.a2a import (
    AgentCard,
    Message,
    Part,
    Role,
    SendMessageResponse,
    Task,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def base_url() -> str:
    return "https://api.test.bud.io"


@pytest.fixture
def client_v10(base_url: str) -> BudClient:
    c = BudClient(api_key="test-key", base_url=base_url, a2a_version="1.0")
    yield c
    c.close()


@pytest.fixture
def client_v03(base_url: str) -> BudClient:
    c = BudClient(api_key="test-key", base_url=base_url, a2a_version="0.3")
    yield c
    c.close()


def jsonrpc_wrap(result: Any) -> dict[str, Any]:
    """Wrap a result in a JSON-RPC 2.0 success response."""
    return {"jsonrpc": "2.0", "id": "1", "result": result}


@pytest.fixture
def sample_task_v03() -> dict[str, Any]:
    return {
        "id": "task-001",
        "contextId": "ctx-001",
        "status": {"state": "completed", "timestamp": "2024-01-01T00:00:00Z"},
        "artifacts": [
            {
                "artifactId": "art-001",
                "parts": [{"kind": "text", "text": "Hello from agent"}],
            }
        ],
    }


@pytest.fixture
def sample_task_v10() -> dict[str, Any]:
    return {
        "id": "task-001",
        "contextId": "ctx-001",
        "status": {
            "state": "TASK_STATE_COMPLETED",
            "timestamp": "2024-01-01T00:00:00Z",
        },
        "artifacts": [
            {
                "artifactId": "art-001",
                "parts": [{"text": "Hello from agent"}],
            }
        ],
    }


@pytest.fixture
def sample_agent_card_v03() -> dict[str, Any]:
    return {
        "name": "Test Agent",
        "description": "A test agent",
        "url": "https://agent.example.com",
        "protocolVersion": "0.3",
        "version": "1.0.0",
        "capabilities": {"streaming": True},
        "skills": [
            {"id": "echo", "name": "Echo", "description": "Echoes input"}
        ],
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
    }


@pytest.fixture
def sample_agent_card_v10() -> dict[str, Any]:
    return {
        "name": "Test Agent",
        "description": "A test agent",
        "version": "1.0.0",
        "supportedInterfaces": [
            {
                "url": "https://agent.example.com/a2a/v1",
                "protocolBinding": "JSONRPC",
                "protocolVersion": "1.0",
            }
        ],
        "capabilities": {"streaming": True},
        "skills": [
            {"id": "echo", "name": "Echo", "description": "Echoes input"}
        ],
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
    }


# ---------------------------------------------------------------------------
# Model dual-format parsing tests
# ---------------------------------------------------------------------------


class TestPartModel:
    def test_part_from_v03_text(self) -> None:
        part = Part.model_validate({"kind": "text", "text": "hello"})
        assert part.text == "hello"
        assert part.raw is None

    def test_part_from_v10_text(self) -> None:
        part = Part.model_validate({"text": "hello"})
        assert part.text == "hello"

    def test_part_from_v03_file(self) -> None:
        part = Part.model_validate(
            {"kind": "file", "file": {"bytes": "aGVsbG8=", "name": "f.txt", "mimeType": "text/plain"}}
        )
        assert part.raw == "aGVsbG8="
        assert part.filename == "f.txt"
        assert part.media_type == "text/plain"

    def test_part_from_v10_file(self) -> None:
        part = Part.model_validate(
            {"raw": "aGVsbG8=", "filename": "f.txt", "mediaType": "text/plain"}
        )
        assert part.raw == "aGVsbG8="
        assert part.filename == "f.txt"
        assert part.media_type == "text/plain"

    def test_part_from_v03_data(self) -> None:
        part = Part.model_validate({"kind": "data", "data": {"key": "value"}})
        assert part.data == {"key": "value"}

    def test_part_from_v10_data(self) -> None:
        part = Part.model_validate({"data": {"key": "value"}})
        assert part.data == {"key": "value"}


class TestEnumNormalization:
    def test_task_state_v03(self) -> None:
        ts = TaskStatus.model_validate({"state": "submitted"})
        assert ts.state == TaskState.SUBMITTED

    def test_task_state_v10(self) -> None:
        ts = TaskStatus.model_validate({"state": "TASK_STATE_SUBMITTED"})
        assert ts.state == TaskState.SUBMITTED

    def test_task_state_completed_v10(self) -> None:
        ts = TaskStatus.model_validate({"state": "TASK_STATE_COMPLETED"})
        assert ts.state == TaskState.COMPLETED

    def test_task_state_input_required_v10(self) -> None:
        ts = TaskStatus.model_validate({"state": "TASK_STATE_INPUT_REQUIRED"})
        assert ts.state == TaskState.INPUT_REQUIRED

    def test_role_v03(self) -> None:
        msg = Message.model_validate(
            {"role": "user", "parts": [{"text": "hi"}]}
        )
        assert msg.role == Role.USER

    def test_role_v10(self) -> None:
        msg = Message.model_validate(
            {"role": "ROLE_USER", "parts": [{"text": "hi"}]}
        )
        assert msg.role == Role.USER

    def test_role_agent_v10(self) -> None:
        msg = Message.model_validate(
            {"role": "ROLE_AGENT", "parts": [{"text": "hi"}]}
        )
        assert msg.role == Role.AGENT


class TestTaskModel:
    def test_task_v03(self, sample_task_v03: dict[str, Any]) -> None:
        task = Task.model_validate(sample_task_v03)
        assert task.id == "task-001"
        assert task.status.state == TaskState.COMPLETED
        assert task.artifacts is not None
        assert task.artifacts[0].parts[0].text == "Hello from agent"

    def test_task_v10(self, sample_task_v10: dict[str, Any]) -> None:
        task = Task.model_validate(sample_task_v10)
        assert task.id == "task-001"
        assert task.status.state == TaskState.COMPLETED
        assert task.artifacts is not None
        assert task.artifacts[0].parts[0].text == "Hello from agent"

    def test_task_extra_fields(self) -> None:
        """Extra fields are preserved (forward compatibility)."""
        task = Task.model_validate(
            {
                "id": "t1",
                "status": {"state": "working"},
                "future_field": "preserved",
            }
        )
        assert task.id == "t1"


class TestAgentCard:
    def test_agent_card_v03(self, sample_agent_card_v03: dict[str, Any]) -> None:
        card = AgentCard.model_validate(sample_agent_card_v03)
        assert card.name == "Test Agent"
        assert card.url == "https://agent.example.com"
        assert card.protocol_version == "0.3"
        assert card.capabilities is not None
        assert card.capabilities.streaming is True

    def test_agent_card_v10(self, sample_agent_card_v10: dict[str, Any]) -> None:
        card = AgentCard.model_validate(sample_agent_card_v10)
        assert card.name == "Test Agent"
        assert card.supported_interfaces is not None
        assert len(card.supported_interfaces) == 1
        assert card.supported_interfaces[0].protocol_binding == "JSONRPC"


# ---------------------------------------------------------------------------
# JSON-RPC helpers tests
# ---------------------------------------------------------------------------


class TestJsonRpc:
    def test_build_request_structure(self) -> None:
        req = build_request("SendMessage", {"message": {}})
        assert req["jsonrpc"] == "2.0"
        assert req["method"] == "SendMessage"
        assert req["params"] == {"message": {}}
        assert isinstance(req["id"], str)
        assert len(req["id"]) > 0

    def test_build_request_custom_id(self) -> None:
        req = build_request("GetTask", {"id": "t1"}, request_id="my-id")
        assert req["id"] == "my-id"

    def test_unwrap_response_success(self) -> None:
        data = {"jsonrpc": "2.0", "id": "1", "result": {"id": "t1"}}
        result = unwrap_response(data)
        assert result == {"id": "t1"}

    def test_unwrap_response_error_raises_jsonrpc_error(self) -> None:
        data = {
            "jsonrpc": "2.0",
            "id": "1",
            "error": {"code": -32001, "message": "Task not found"},
        }
        with pytest.raises(A2AError) as exc_info:
            unwrap_response(data)
        assert exc_info.value.code == -32001
        assert "Task not found" in str(exc_info.value)

    def test_unwrap_response_malformed(self) -> None:
        with pytest.raises(A2AError, match="missing both"):
            unwrap_response({"jsonrpc": "2.0", "id": "1"})

    def test_unwrap_response_non_dict(self) -> None:
        with pytest.raises(A2AError, match="Expected JSON-RPC response dict"):
            unwrap_response("not a dict")


# ---------------------------------------------------------------------------
# Resource tests — v1.0
# ---------------------------------------------------------------------------


class TestA2AResourceV10:
    @respx.mock
    def test_get_agent_card(
        self, client_v10: BudClient, base_url: str, sample_agent_card_v10: dict[str, Any]
    ) -> None:
        route = respx.get(f"{base_url}/a2a/my-agent/v0/.well-known/agent-card.json").mock(
            return_value=Response(200, json=sample_agent_card_v10)
        )
        card = client_v10.a2a.get_agent_card("my-agent")
        assert card.name == "Test Agent"
        # Verify A2A-Version header
        request = route.calls.last.request
        assert request.headers.get("a2a-version") == "1.0"

    @respx.mock
    def test_get_agent_card_with_version(
        self, client_v10: BudClient, base_url: str, sample_agent_card_v10: dict[str, Any]
    ) -> None:
        respx.get(f"{base_url}/a2a/my-agent/v2/.well-known/agent-card.json").mock(
            return_value=Response(200, json=sample_agent_card_v10)
        )
        card = client_v10.a2a.get_agent_card("my-agent", version=2)
        assert card.name == "Test Agent"

    @respx.mock
    def test_send_message_text(
        self, client_v10: BudClient, base_url: str, sample_task_v10: dict[str, Any]
    ) -> None:
        route = respx.post(f"{base_url}/a2a/my-agent/v0/").mock(
            return_value=Response(200, json=jsonrpc_wrap({"task": sample_task_v10}))
        )
        result = client_v10.a2a.send_message("my-agent", message="Hello!")
        assert isinstance(result, SendMessageResponse)
        assert result.task is not None
        assert result.task.id == "task-001"

        # Verify JSON-RPC envelope
        request = route.calls.last.request
        payload = json.loads(request.content)
        assert payload["method"] == "SendMessage"
        assert payload["jsonrpc"] == "2.0"
        assert "id" in payload

    @respx.mock
    def test_send_message_v10_part_format(
        self, client_v10: BudClient, base_url: str, sample_task_v10: dict[str, Any]
    ) -> None:
        route = respx.post(f"{base_url}/a2a/my-agent/v0/").mock(
            return_value=Response(200, json=jsonrpc_wrap({"task": sample_task_v10}))
        )
        client_v10.a2a.send_message("my-agent", message="Hello!")

        # Verify v1.0 Part format (no "kind" field)
        payload = json.loads(route.calls.last.request.content)
        msg = payload["params"]["message"]
        assert msg["role"] == "ROLE_USER"
        assert msg["parts"][0] == {"text": "Hello!"}

    @respx.mock
    def test_send_message_with_context_id(
        self, client_v10: BudClient, base_url: str, sample_task_v10: dict[str, Any]
    ) -> None:
        route = respx.post(f"{base_url}/a2a/my-agent/v0/").mock(
            return_value=Response(200, json=jsonrpc_wrap({"task": sample_task_v10}))
        )
        client_v10.a2a.send_message(
            "my-agent", message="EUR", context_id="ctx-001", task_id="task-001"
        )
        payload = json.loads(route.calls.last.request.content)
        msg = payload["params"]["message"]
        assert msg["contextId"] == "ctx-001"
        assert msg["taskId"] == "task-001"

    @respx.mock
    def test_get_task(
        self, client_v10: BudClient, base_url: str, sample_task_v10: dict[str, Any]
    ) -> None:
        route = respx.post(f"{base_url}/a2a/my-agent/v0/").mock(
            return_value=Response(200, json=jsonrpc_wrap(sample_task_v10))
        )
        task = client_v10.a2a.get_task("my-agent", task_id="task-001")
        assert task.id == "task-001"

        payload = json.loads(route.calls.last.request.content)
        assert payload["method"] == "GetTask"
        assert payload["params"]["id"] == "task-001"

    @respx.mock
    def test_cancel_task(
        self, client_v10: BudClient, base_url: str, sample_task_v10: dict[str, Any]
    ) -> None:
        route = respx.post(f"{base_url}/a2a/my-agent/v0/").mock(
            return_value=Response(200, json=jsonrpc_wrap(sample_task_v10))
        )
        task = client_v10.a2a.cancel_task("my-agent", task_id="task-001")
        assert task.id == "task-001"

        payload = json.loads(route.calls.last.request.content)
        assert payload["method"] == "CancelTask"

    @respx.mock
    def test_default_v0_path(
        self, client_v10: BudClient, base_url: str, sample_task_v10: dict[str, Any]
    ) -> None:
        route = respx.post(f"{base_url}/a2a/my-agent/v0/").mock(
            return_value=Response(200, json=jsonrpc_wrap({"task": sample_task_v10}))
        )
        client_v10.a2a.send_message("my-agent", message="test")
        assert "/v0/" in str(route.calls.last.request.url)

    @respx.mock
    def test_explicit_version_path(
        self, client_v10: BudClient, base_url: str, sample_task_v10: dict[str, Any]
    ) -> None:
        route = respx.post(f"{base_url}/a2a/my-agent/v2/").mock(
            return_value=Response(200, json=jsonrpc_wrap({"task": sample_task_v10}))
        )
        client_v10.a2a.send_message("my-agent", message="test", version=2)
        assert "/v2/" in str(route.calls.last.request.url)

    @respx.mock
    def test_jsonrpc_error_raises(
        self, client_v10: BudClient, base_url: str
    ) -> None:
        respx.post(f"{base_url}/a2a/my-agent/v0/").mock(
            return_value=Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": "1",
                    "error": {"code": -32001, "message": "Task not found"},
                },
            )
        )
        with pytest.raises(A2AError) as exc_info:
            client_v10.a2a.send_message("my-agent", message="hello")
        assert exc_info.value.code == -32001


# ---------------------------------------------------------------------------
# Resource tests — v0.3
# ---------------------------------------------------------------------------


class TestA2AResourceV03:
    @respx.mock
    def test_send_message_v03_method(
        self, client_v03: BudClient, base_url: str, sample_task_v03: dict[str, Any]
    ) -> None:
        route = respx.post(f"{base_url}/a2a/my-agent/v0/").mock(
            return_value=Response(200, json=jsonrpc_wrap(sample_task_v03))
        )
        client_v03.a2a.send_message("my-agent", message="Hello!")

        payload = json.loads(route.calls.last.request.content)
        assert payload["method"] == "message/send"

    @respx.mock
    def test_send_message_v03_part_format(
        self, client_v03: BudClient, base_url: str, sample_task_v03: dict[str, Any]
    ) -> None:
        route = respx.post(f"{base_url}/a2a/my-agent/v0/").mock(
            return_value=Response(200, json=jsonrpc_wrap(sample_task_v03))
        )
        client_v03.a2a.send_message("my-agent", message="Hello!")

        payload = json.loads(route.calls.last.request.content)
        msg = payload["params"]["message"]
        assert msg["parts"][0] == {"kind": "text", "text": "Hello!"}

    @respx.mock
    def test_send_message_v03_role_format(
        self, client_v03: BudClient, base_url: str, sample_task_v03: dict[str, Any]
    ) -> None:
        route = respx.post(f"{base_url}/a2a/my-agent/v0/").mock(
            return_value=Response(200, json=jsonrpc_wrap(sample_task_v03))
        )
        client_v03.a2a.send_message("my-agent", message="Hello!")

        payload = json.loads(route.calls.last.request.content)
        msg = payload["params"]["message"]
        assert msg["role"] == "user"

    @respx.mock
    def test_get_task_v03_method(
        self, client_v03: BudClient, base_url: str, sample_task_v03: dict[str, Any]
    ) -> None:
        route = respx.post(f"{base_url}/a2a/my-agent/v0/").mock(
            return_value=Response(200, json=jsonrpc_wrap(sample_task_v03))
        )
        client_v03.a2a.get_task("my-agent", task_id="task-001")

        payload = json.loads(route.calls.last.request.content)
        assert payload["method"] == "tasks/get"

    @respx.mock
    def test_send_message_v03_response_parsing(
        self, client_v03: BudClient, base_url: str, sample_task_v03: dict[str, Any]
    ) -> None:
        """v0.3 returns Task directly (no wrapper)."""
        respx.post(f"{base_url}/a2a/my-agent/v0/").mock(
            return_value=Response(200, json=jsonrpc_wrap(sample_task_v03))
        )
        result = client_v03.a2a.send_message("my-agent", message="Hello!")
        assert result.task is not None
        assert result.task.id == "task-001"
        assert result.task.status.state == TaskState.COMPLETED


# ---------------------------------------------------------------------------
# Streaming tests
# ---------------------------------------------------------------------------


def _build_sse(events: list[dict[str, Any]]) -> bytes:
    """Build SSE byte content from a list of JSON-RPC responses."""
    lines = []
    for event in events:
        lines.append(f"data: {json.dumps(event)}\n\n")
    lines.append("data: [DONE]\n\n")
    return "".join(lines).encode()


class TestA2AStreaming:
    @respx.mock
    def test_stream_v10_events(
        self, client_v10: BudClient, base_url: str
    ) -> None:
        sse_events = [
            jsonrpc_wrap(
                {
                    "task": {
                        "id": "t1",
                        "contextId": "c1",
                        "status": {"state": "TASK_STATE_WORKING"},
                    }
                }
            ),
            jsonrpc_wrap(
                {
                    "statusUpdate": {
                        "taskId": "t1",
                        "contextId": "c1",
                        "status": {"state": "TASK_STATE_COMPLETED"},
                    }
                }
            ),
        ]
        respx.post(f"{base_url}/a2a/my-agent/v0/").mock(
            return_value=Response(
                200,
                content=_build_sse(sse_events),
                headers={"Content-Type": "text/event-stream"},
            )
        )
        stream = client_v10.a2a.send_message("my-agent", message="hello", stream=True)
        events = list(stream)
        assert len(events) == 2
        assert isinstance(events[0], Task)
        assert isinstance(events[1], TaskStatusUpdateEvent)

    @respx.mock
    def test_stream_v03_events(
        self, client_v03: BudClient, base_url: str
    ) -> None:
        sse_events = [
            jsonrpc_wrap(
                {
                    "kind": "task",
                    "id": "t1",
                    "contextId": "c1",
                    "status": {"state": "working"},
                }
            ),
            jsonrpc_wrap(
                {
                    "kind": "status-update",
                    "taskId": "t1",
                    "contextId": "c1",
                    "status": {"state": "completed"},
                    "final": True,
                }
            ),
        ]
        respx.post(f"{base_url}/a2a/my-agent/v0/").mock(
            return_value=Response(
                200,
                content=_build_sse(sse_events),
                headers={"Content-Type": "text/event-stream"},
            )
        )
        stream = client_v03.a2a.send_message("my-agent", message="hello", stream=True)
        events = list(stream)
        assert len(events) == 2
        assert isinstance(events[0], Task)
        assert isinstance(events[1], TaskStatusUpdateEvent)
        assert events[1].final is True

    @respx.mock
    def test_stream_final_task(
        self, client_v10: BudClient, base_url: str
    ) -> None:
        sse_events = [
            jsonrpc_wrap(
                {
                    "task": {
                        "id": "t1",
                        "status": {"state": "TASK_STATE_COMPLETED"},
                    }
                }
            ),
        ]
        respx.post(f"{base_url}/a2a/my-agent/v0/").mock(
            return_value=Response(
                200,
                content=_build_sse(sse_events),
                headers={"Content-Type": "text/event-stream"},
            )
        )
        stream = client_v10.a2a.send_message("my-agent", message="hello", stream=True)
        list(stream)  # consume
        assert stream.final_task is not None
        assert stream.final_task.id == "t1"

    @respx.mock
    def test_stream_jsonrpc_error_raises(
        self, client_v10: BudClient, base_url: str
    ) -> None:
        sse_events = [
            {
                "jsonrpc": "2.0",
                "id": "1",
                "error": {"code": -32603, "message": "Internal error"},
            },
        ]
        respx.post(f"{base_url}/a2a/my-agent/v0/").mock(
            return_value=Response(
                200,
                content=_build_sse(sse_events),
                headers={"Content-Type": "text/event-stream"},
            )
        )
        stream = client_v10.a2a.send_message("my-agent", message="hello", stream=True)
        with pytest.raises(A2AError) as exc_info:
            list(stream)
        assert exc_info.value.code == -32603


# ---------------------------------------------------------------------------
# Error and edge case tests
# ---------------------------------------------------------------------------


class TestA2AErrors:
    @respx.mock
    def test_http_401_raises_auth_error(
        self, client_v10: BudClient, base_url: str
    ) -> None:
        from bud.exceptions import AuthenticationError

        respx.post(f"{base_url}/a2a/my-agent/v0/").mock(
            return_value=Response(401, json={"message": "Unauthorized"})
        )
        with pytest.raises(AuthenticationError):
            client_v10.a2a.send_message("my-agent", message="hello")

    def test_unsupported_version_raises(self, client_v10: BudClient) -> None:
        with pytest.raises(ValueError, match="Unsupported A2A version"):
            client_v10.a2a.a2a_version = "2.0"

    @respx.mock
    def test_send_message_response_with_task(
        self, client_v10: BudClient, base_url: str, sample_task_v10: dict[str, Any]
    ) -> None:
        respx.post(f"{base_url}/a2a/my-agent/v0/").mock(
            return_value=Response(200, json=jsonrpc_wrap({"task": sample_task_v10}))
        )
        result = client_v10.a2a.send_message("my-agent", message="hello")
        assert result.task is not None
        assert result.message is None

    @respx.mock
    def test_send_message_response_with_message(
        self, client_v10: BudClient, base_url: str
    ) -> None:
        msg = {
            "messageId": "m1",
            "role": "ROLE_AGENT",
            "parts": [{"text": "Direct response"}],
        }
        respx.post(f"{base_url}/a2a/my-agent/v0/").mock(
            return_value=Response(200, json=jsonrpc_wrap({"message": msg}))
        )
        result = client_v10.a2a.send_message("my-agent", message="hello")
        assert result.message is not None
        assert result.task is None
        assert result.message.parts[0].text == "Direct response"

    @respx.mock
    def test_a2a_version_header_v03(
        self, client_v03: BudClient, base_url: str, sample_task_v03: dict[str, Any]
    ) -> None:
        route = respx.post(f"{base_url}/a2a/my-agent/v0/").mock(
            return_value=Response(200, json=jsonrpc_wrap(sample_task_v03))
        )
        client_v03.a2a.send_message("my-agent", message="hello")
        request = route.calls.last.request
        assert request.headers.get("a2a-version") == "0.3"


# ---------------------------------------------------------------------------
# Tenant parameter tests
# ---------------------------------------------------------------------------


class TestTenantParam:
    @respx.mock
    def test_get_task_with_tenant(
        self, client_v10: BudClient, base_url: str, sample_task_v10: dict[str, Any]
    ) -> None:
        route = respx.post(f"{base_url}/a2a/my-agent/v0/").mock(
            return_value=Response(200, json=jsonrpc_wrap(sample_task_v10))
        )
        client_v10.a2a.get_task("my-agent", task_id="task-001", tenant="t1")
        payload = json.loads(route.calls.last.request.content)
        assert payload["params"]["tenant"] == "t1"

    @respx.mock
    def test_cancel_task_with_tenant(
        self, client_v10: BudClient, base_url: str, sample_task_v10: dict[str, Any]
    ) -> None:
        route = respx.post(f"{base_url}/a2a/my-agent/v0/").mock(
            return_value=Response(200, json=jsonrpc_wrap(sample_task_v10))
        )
        client_v10.a2a.cancel_task("my-agent", task_id="task-001", tenant="t1")
        payload = json.loads(route.calls.last.request.content)
        assert payload["params"]["tenant"] == "t1"


# ---------------------------------------------------------------------------
# ListTasks tests
# ---------------------------------------------------------------------------


class TestListTasks:
    @respx.mock
    def test_list_tasks_basic(
        self, client_v10: BudClient, base_url: str, sample_task_v10: dict[str, Any]
    ) -> None:
        from bud.models.a2a import ListTasksResponse

        result_data = {
            "tasks": [sample_task_v10],
            "nextPageToken": "cursor-abc",
            "pageSize": 50,
            "totalSize": 1,
        }
        respx.post(f"{base_url}/a2a/my-agent/v0/").mock(
            return_value=Response(200, json=jsonrpc_wrap(result_data))
        )
        result = client_v10.a2a.list_tasks("my-agent")
        assert isinstance(result, ListTasksResponse)
        assert len(result.tasks) == 1
        assert result.tasks[0].id == "task-001"
        assert result.next_page_token == "cursor-abc"
        assert result.page_size == 50
        assert result.total_size == 1

    @respx.mock
    def test_list_tasks_method_name(
        self, client_v10: BudClient, base_url: str
    ) -> None:
        result_data = {"tasks": [], "nextPageToken": "", "pageSize": 0, "totalSize": 0}
        route = respx.post(f"{base_url}/a2a/my-agent/v0/").mock(
            return_value=Response(200, json=jsonrpc_wrap(result_data))
        )
        client_v10.a2a.list_tasks("my-agent")
        payload = json.loads(route.calls.last.request.content)
        assert payload["method"] == "ListTasks"

    @respx.mock
    def test_list_tasks_with_filters(
        self, client_v10: BudClient, base_url: str
    ) -> None:
        result_data = {"tasks": [], "nextPageToken": "", "pageSize": 10, "totalSize": 0}
        route = respx.post(f"{base_url}/a2a/my-agent/v0/").mock(
            return_value=Response(200, json=jsonrpc_wrap(result_data))
        )
        client_v10.a2a.list_tasks(
            "my-agent",
            context_id="ctx-001",
            status=TaskState.WORKING,
            page_size=10,
        )
        payload = json.loads(route.calls.last.request.content)
        params = payload["params"]
        assert params["contextId"] == "ctx-001"
        assert params["status"] == "TASK_STATE_WORKING"
        assert params["pageSize"] == 10

    @respx.mock
    def test_list_tasks_with_pagination(
        self, client_v10: BudClient, base_url: str
    ) -> None:
        result_data = {"tasks": [], "nextPageToken": "", "pageSize": 50, "totalSize": 0}
        route = respx.post(f"{base_url}/a2a/my-agent/v0/").mock(
            return_value=Response(200, json=jsonrpc_wrap(result_data))
        )
        client_v10.a2a.list_tasks("my-agent", page_token="cursor-xyz")
        payload = json.loads(route.calls.last.request.content)
        assert payload["params"]["pageToken"] == "cursor-xyz"

    def test_list_tasks_v03_raises(self, client_v03: BudClient) -> None:
        with pytest.raises(A2AError, match="only available in A2A v1.0"):
            client_v03.a2a.list_tasks("my-agent")

    @respx.mock
    def test_list_tasks_empty(
        self, client_v10: BudClient, base_url: str
    ) -> None:
        result_data = {"tasks": [], "nextPageToken": "", "pageSize": 0, "totalSize": 0}
        respx.post(f"{base_url}/a2a/my-agent/v0/").mock(
            return_value=Response(200, json=jsonrpc_wrap(result_data))
        )
        result = client_v10.a2a.list_tasks("my-agent")
        assert result.tasks == []
        assert result.next_page_token == ""


# ---------------------------------------------------------------------------
# SubscribeToTask tests
# ---------------------------------------------------------------------------


class TestSubscribeToTask:
    @respx.mock
    def test_subscribe_v10_method(
        self, client_v10: BudClient, base_url: str
    ) -> None:
        sse_events = [
            jsonrpc_wrap(
                {
                    "task": {
                        "id": "t1",
                        "status": {"state": "TASK_STATE_WORKING"},
                    }
                }
            ),
        ]
        route = respx.post(f"{base_url}/a2a/my-agent/v0/").mock(
            return_value=Response(
                200,
                content=_build_sse(sse_events),
                headers={"Content-Type": "text/event-stream"},
            )
        )
        stream = client_v10.a2a.subscribe_to_task("my-agent", task_id="task-001")
        list(stream)  # consume
        payload = json.loads(route.calls.last.request.content)
        assert payload["method"] == "SubscribeToTask"
        assert payload["params"]["id"] == "task-001"

    @respx.mock
    def test_subscribe_v03_method(
        self, client_v03: BudClient, base_url: str
    ) -> None:
        sse_events = [
            jsonrpc_wrap(
                {"kind": "task", "id": "t1", "status": {"state": "working"}}
            ),
        ]
        route = respx.post(f"{base_url}/a2a/my-agent/v0/").mock(
            return_value=Response(
                200,
                content=_build_sse(sse_events),
                headers={"Content-Type": "text/event-stream"},
            )
        )
        stream = client_v03.a2a.subscribe_to_task("my-agent", task_id="task-001")
        list(stream)
        payload = json.loads(route.calls.last.request.content)
        assert payload["method"] == "tasks/resubscribe"

    @respx.mock
    def test_subscribe_returns_stream(
        self, client_v10: BudClient, base_url: str
    ) -> None:
        from bud._a2a_streaming import A2AStream

        sse_events = [
            jsonrpc_wrap(
                {
                    "task": {
                        "id": "t1",
                        "status": {"state": "TASK_STATE_COMPLETED"},
                    }
                }
            ),
        ]
        respx.post(f"{base_url}/a2a/my-agent/v0/").mock(
            return_value=Response(
                200,
                content=_build_sse(sse_events),
                headers={"Content-Type": "text/event-stream"},
            )
        )
        stream = client_v10.a2a.subscribe_to_task("my-agent", task_id="t1")
        assert isinstance(stream, A2AStream)
        events = list(stream)
        assert len(events) == 1
        assert isinstance(events[0], Task)

    @respx.mock
    def test_subscribe_with_tenant(
        self, client_v10: BudClient, base_url: str
    ) -> None:
        sse_events = [
            jsonrpc_wrap(
                {"task": {"id": "t1", "status": {"state": "TASK_STATE_WORKING"}}}
            ),
        ]
        route = respx.post(f"{base_url}/a2a/my-agent/v0/").mock(
            return_value=Response(
                200,
                content=_build_sse(sse_events),
                headers={"Content-Type": "text/event-stream"},
            )
        )
        stream = client_v10.a2a.subscribe_to_task(
            "my-agent", task_id="t1", tenant="t1"
        )
        list(stream)
        payload = json.loads(route.calls.last.request.content)
        assert payload["params"]["tenant"] == "t1"


# ---------------------------------------------------------------------------
# GetExtendedAgentCard tests
# ---------------------------------------------------------------------------


class TestGetExtendedAgentCard:
    @respx.mock
    def test_get_extended_card_v10(
        self, client_v10: BudClient, base_url: str, sample_agent_card_v10: dict[str, Any]
    ) -> None:
        route = respx.post(f"{base_url}/a2a/my-agent/v0/").mock(
            return_value=Response(200, json=jsonrpc_wrap(sample_agent_card_v10))
        )
        card = client_v10.a2a.get_extended_agent_card("my-agent")
        assert isinstance(card, AgentCard)
        assert card.name == "Test Agent"
        payload = json.loads(route.calls.last.request.content)
        assert payload["method"] == "GetExtendedAgentCard"

    @respx.mock
    def test_get_extended_card_v03(
        self, client_v03: BudClient, base_url: str, sample_agent_card_v03: dict[str, Any]
    ) -> None:
        route = respx.post(f"{base_url}/a2a/my-agent/v0/").mock(
            return_value=Response(200, json=jsonrpc_wrap(sample_agent_card_v03))
        )
        card = client_v03.a2a.get_extended_agent_card("my-agent")
        assert card.name == "Test Agent"
        payload = json.loads(route.calls.last.request.content)
        assert payload["method"] == "agent/getAuthenticatedExtendedCard"

    @respx.mock
    def test_get_extended_card_with_tenant(
        self, client_v10: BudClient, base_url: str, sample_agent_card_v10: dict[str, Any]
    ) -> None:
        route = respx.post(f"{base_url}/a2a/my-agent/v0/").mock(
            return_value=Response(200, json=jsonrpc_wrap(sample_agent_card_v10))
        )
        client_v10.a2a.get_extended_agent_card("my-agent", tenant="t1")
        payload = json.loads(route.calls.last.request.content)
        assert payload["params"]["tenant"] == "t1"

    @respx.mock
    def test_get_extended_card_is_post(
        self, client_v10: BudClient, base_url: str, sample_agent_card_v10: dict[str, Any]
    ) -> None:
        """Extended card uses JSON-RPC POST, not GET like get_agent_card."""
        route = respx.post(f"{base_url}/a2a/my-agent/v0/").mock(
            return_value=Response(200, json=jsonrpc_wrap(sample_agent_card_v10))
        )
        client_v10.a2a.get_extended_agent_card("my-agent")
        assert route.calls.last.request.method == "POST"


# ---------------------------------------------------------------------------
# ListTasksResponse model test
# ---------------------------------------------------------------------------


class TestListTasksResponseModel:
    def test_list_tasks_response_parse(self) -> None:
        from bud.models.a2a import ListTasksResponse

        data = {
            "tasks": [
                {"id": "t1", "status": {"state": "completed"}},
                {"id": "t2", "status": {"state": "working"}},
            ],
            "nextPageToken": "abc",
            "pageSize": 50,
            "totalSize": 100,
        }
        resp = ListTasksResponse.model_validate(data)
        assert len(resp.tasks) == 2
        assert resp.next_page_token == "abc"
        assert resp.page_size == 50
        assert resp.total_size == 100
