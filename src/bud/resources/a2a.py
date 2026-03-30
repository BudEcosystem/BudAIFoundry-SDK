"""A2A (Agent-to-Agent) protocol resource.

Provides sync and async resources for interacting with A2A agents
via the BudAI gateway. Supports both A2A v0.3 and v1.0 protocols.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, overload

from bud._jsonrpc import build_request, unwrap_response
from bud.exceptions import A2AError
from bud.models.a2a import (
    AgentCard,
    ListTasksResponse,
    Message,
    Part,
    Role,
    SendMessageConfiguration,
    SendMessageResponse,
    Task,
    TaskState,
)
from bud.resources._base import AsyncResource, SyncResource

if TYPE_CHECKING:
    from bud._a2a_streaming import A2AStream, AsyncA2AStream
    from bud._http import AsyncHttpClient, HttpClient

# ---------------------------------------------------------------------------
# Version constants
# ---------------------------------------------------------------------------

A2A_V03 = "0.3"
A2A_V10 = "1.0"
A2A_DEFAULT_VERSION = A2A_V03

_METHOD_NAMES: dict[str, dict[str, str]] = {
    A2A_V03: {
        "send": "message/send",
        "stream": "message/stream",
        "get_task": "tasks/get",
        "cancel_task": "tasks/cancel",
        "get_card": "agent/getAuthenticatedExtendedCard",
        "subscribe_to_task": "tasks/resubscribe",
    },
    A2A_V10: {
        "send": "SendMessage",
        "stream": "SendStreamingMessage",
        "get_task": "GetTask",
        "cancel_task": "CancelTask",
        "get_card": "GetExtendedAgentCard",
        "subscribe_to_task": "SubscribeToTask",
        "list_tasks": "ListTasks",
    },
}

# Reverse maps for serialization to v1.0 wire format
_CANONICAL_TO_V1_ROLE: dict[str, str] = {
    "user": "ROLE_USER",
    "agent": "ROLE_AGENT",
}

_CANONICAL_TO_V1_STATE: dict[str, str] = {
    "submitted": "TASK_STATE_SUBMITTED",
    "working": "TASK_STATE_WORKING",
    "input-required": "TASK_STATE_INPUT_REQUIRED",
    "completed": "TASK_STATE_COMPLETED",
    "failed": "TASK_STATE_FAILED",
    "canceled": "TASK_STATE_CANCELED",
    "rejected": "TASK_STATE_REJECTED",
    "auth-required": "TASK_STATE_AUTH_REQUIRED",
    "unknown": "TASK_STATE_UNSPECIFIED",
}


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _a2a_path(agent_name: str, version: int | None = None) -> str:
    """Build the gateway path for an A2A agent."""
    v = f"v{version}" if version is not None else "v0"
    return f"/a2a/{agent_name}/{v}"


def _agent_card_path(agent_name: str, version: int | None = None) -> str:
    """Build the agent card discovery path."""
    return f"{_a2a_path(agent_name, version)}/.well-known/agent-card.json"


# ---------------------------------------------------------------------------
# Serialization helpers (version-aware)
# ---------------------------------------------------------------------------


def _serialize_role(role: str, a2a_version: str) -> str:
    """Serialize role to wire format."""
    if a2a_version == A2A_V10:
        return _CANONICAL_TO_V1_ROLE.get(role, role)
    return role


def _serialize_part(part: Part, a2a_version: str) -> dict[str, Any]:
    """Serialize a Part to version-appropriate wire format."""
    if a2a_version == A2A_V03:
        if part.text is not None:
            d: dict[str, Any] = {"kind": "text", "text": part.text}
            if part.metadata:
                d["metadata"] = part.metadata
            return d
        if part.raw is not None:
            file_data: dict[str, Any] = {"bytes": part.raw}
            if part.filename:
                file_data["name"] = part.filename
            if part.media_type:
                file_data["mimeType"] = part.media_type
            return {"kind": "file", "file": file_data}
        if part.url is not None:
            file_data = {"uri": part.url}
            if part.filename:
                file_data["name"] = part.filename
            if part.media_type:
                file_data["mimeType"] = part.media_type
            return {"kind": "file", "file": file_data}
        if part.data is not None:
            d = {"kind": "data", "data": part.data}
            if part.metadata:
                d["metadata"] = part.metadata
            return d
        return {}
    # v1.0: use model_dump
    return part.model_dump(by_alias=True, exclude_none=True)


def _serialize_message(message: Message, a2a_version: str) -> dict[str, Any]:
    """Serialize a Message to version-appropriate wire format."""
    # BudModel uses use_enum_values=True, so role is already a string
    role_str = message.role.value if isinstance(message.role, Role) else str(message.role)
    result: dict[str, Any] = {
        "role": _serialize_role(role_str, a2a_version),
        "parts": [_serialize_part(p, a2a_version) for p in message.parts],
    }
    if message.message_id is not None:
        result["messageId"] = message.message_id
    if message.context_id is not None:
        result["contextId"] = message.context_id
    if message.task_id is not None:
        result["taskId"] = message.task_id
    if message.reference_task_ids is not None:
        result["referenceTaskIds"] = message.reference_task_ids
    if message.metadata is not None:
        result["metadata"] = message.metadata
    if message.extensions is not None:
        result["extensions"] = message.extensions
    return result


def _build_message_params(
    message: str | Message | dict[str, Any],
    *,
    context_id: str | None = None,
    task_id: str | None = None,
    configuration: SendMessageConfiguration | dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    a2a_version: str,
) -> dict[str, Any]:
    """Build JSON-RPC params for send_message / SendMessage."""
    # Normalize message input
    if isinstance(message, str):
        msg = Message(role=Role.USER, parts=[Part(text=message)])
    elif isinstance(message, dict):
        msg = Message.model_validate(message)
    else:
        msg = message

    # Override context_id / task_id if provided
    if context_id is not None:
        msg = msg.model_copy(update={"context_id": context_id})
    if task_id is not None:
        msg = msg.model_copy(update={"task_id": task_id})

    params: dict[str, Any] = {
        "message": _serialize_message(msg, a2a_version),
    }

    if configuration is not None:
        if isinstance(configuration, dict):
            params["configuration"] = configuration
        else:
            params["configuration"] = configuration.model_dump(
                by_alias=True, exclude_none=True
            )

    if metadata is not None:
        params["metadata"] = metadata

    return params


def _parse_send_response(result: dict[str, Any]) -> SendMessageResponse:
    """Parse the JSON-RPC result into a SendMessageResponse.

    Handles both wrapped (``{"task": {...}}``) and unwrapped (direct Task/Message)
    response formats, since the bud-gateway may return either depending on version
    and configuration.
    """
    # Try wrapped format first (v1.0 spec: {"task": {...}} or {"message": {...}})
    if "task" in result and isinstance(result["task"], dict):
        return SendMessageResponse.model_validate(result)
    if "message" in result and isinstance(result.get("message"), dict) and "parts" in result["message"]:
        return SendMessageResponse.model_validate(result)
    # Unwrapped: server returned Task or Message directly
    if "status" in result and "id" in result:
        return SendMessageResponse(task=Task.model_validate(result), message=None)
    if "role" in result and "parts" in result:
        return SendMessageResponse(task=None, message=Message.model_validate(result))
    # Last resort
    return SendMessageResponse.model_validate(result)


# ---------------------------------------------------------------------------
# Sync resource
# ---------------------------------------------------------------------------


class A2A(SyncResource):
    """A2A (Agent-to-Agent) protocol resource.

    Interact with A2A agents deployed via the BudAI gateway.

    Example:
        client = BudClient(api_key="...")
        card = client.a2a.get_agent_card("my-agent")
        result = client.a2a.send_message("my-agent", message="Hello!")
    """

    def __init__(self, http: HttpClient, a2a_version: str = A2A_DEFAULT_VERSION) -> None:
        super().__init__(http)
        self._a2a_version = a2a_version

    @property
    def a2a_version(self) -> str:
        """Current A2A protocol version."""
        return self._a2a_version

    @a2a_version.setter
    def a2a_version(self, value: str) -> None:
        if value not in (A2A_V03, A2A_V10):
            raise ValueError(f"Unsupported A2A version: {value!r}. Use '0.3' or '1.0'.")
        self._a2a_version = value

    def _headers(self) -> dict[str, str]:
        return {"A2A-Version": self._a2a_version}

    def _method(self, key: str) -> str:
        return _METHOD_NAMES[self._a2a_version][key]

    def get_agent_card(
        self,
        agent_name: str,
        *,
        version: int | None = None,
    ) -> AgentCard:
        """Discover an agent's capabilities via its Agent Card.

        Args:
            agent_name: Name of the A2A agent.
            version: Agent deployment version (None = latest via v0).

        Returns:
            AgentCard with the agent's metadata.
        """
        path = _agent_card_path(agent_name, version)
        data = self._http.get(path, headers=self._headers())
        return AgentCard.model_validate(data)

    @overload
    def send_message(
        self,
        agent_name: str,
        *,
        message: str | Message | dict[str, Any],
        stream: Literal[False] = False,
        version: int | None = None,
        context_id: str | None = None,
        task_id: str | None = None,
        configuration: SendMessageConfiguration | dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SendMessageResponse: ...

    @overload
    def send_message(
        self,
        agent_name: str,
        *,
        message: str | Message | dict[str, Any],
        stream: Literal[True],
        version: int | None = None,
        context_id: str | None = None,
        task_id: str | None = None,
        configuration: SendMessageConfiguration | dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> A2AStream: ...

    def send_message(
        self,
        agent_name: str,
        *,
        message: str | Message | dict[str, Any],
        stream: bool = False,
        version: int | None = None,
        context_id: str | None = None,
        task_id: str | None = None,
        configuration: SendMessageConfiguration | dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SendMessageResponse | A2AStream:
        """Send a message to an A2A agent.

        Args:
            agent_name: Name of the agent.
            message: Text string, Message object, or dict.
            stream: If True, returns an A2AStream for SSE events.
            version: Agent deployment version (None = latest via v0).
            context_id: Conversation context ID for multi-turn.
            task_id: Existing task ID (for input-required follow-ups).
            configuration: Request configuration (output modes, history, etc).
            metadata: Optional metadata key-value pairs.

        Returns:
            SendMessageResponse if stream=False, A2AStream if stream=True.
        """
        params = _build_message_params(
            message,
            context_id=context_id,
            task_id=task_id,
            configuration=configuration,
            metadata=metadata,
            a2a_version=self._a2a_version,
        )
        method = self._method("stream" if stream else "send")
        path = f"{_a2a_path(agent_name, version)}/"
        envelope = build_request(method, params)

        if stream:
            from bud._a2a_streaming import A2AStream as A2AStreamCls

            response_ctx = self._http.stream(
                "POST", path, json=envelope, headers=self._headers()
            )
            response = response_ctx.__enter__()
            return A2AStreamCls(
                response,
                response_context=response_ctx,
                a2a_version=self._a2a_version,
            )

        data = self._http.post(path, json=envelope, headers=self._headers())
        result = unwrap_response(data)
        return _parse_send_response(result)

    def get_task(
        self,
        agent_name: str,
        *,
        task_id: str,
        version: int | None = None,
        history_length: int | None = None,
        tenant: str | None = None,
    ) -> Task:
        """Get the state of an existing task.

        Args:
            agent_name: Name of the agent.
            task_id: Task identifier.
            version: Agent deployment version.
            history_length: Max history messages to include.
            tenant: Tenant identifier (v1.0 only).

        Returns:
            Current Task state.
        """
        params: dict[str, Any] = {"id": task_id}
        if history_length is not None:
            params["historyLength"] = history_length
        if tenant is not None:
            params["tenant"] = tenant
        path = f"{_a2a_path(agent_name, version)}/"
        envelope = build_request(self._method("get_task"), params)
        data = self._http.post(path, json=envelope, headers=self._headers())
        result = unwrap_response(data)
        return Task.model_validate(result)

    def cancel_task(
        self,
        agent_name: str,
        *,
        task_id: str,
        version: int | None = None,
        tenant: str | None = None,
    ) -> Task:
        """Cancel a running task.

        Args:
            agent_name: Name of the agent.
            task_id: Task identifier.
            version: Agent deployment version.
            tenant: Tenant identifier (v1.0 only).

        Returns:
            Updated Task state.
        """
        params: dict[str, Any] = {"id": task_id}
        if tenant is not None:
            params["tenant"] = tenant
        path = f"{_a2a_path(agent_name, version)}/"
        envelope = build_request(self._method("cancel_task"), params)
        data = self._http.post(path, json=envelope, headers=self._headers())
        result = unwrap_response(data)
        return Task.model_validate(result)

    def list_tasks(
        self,
        agent_name: str,
        *,
        version: int | None = None,
        tenant: str | None = None,
        context_id: str | None = None,
        status: TaskState | str | None = None,
        page_size: int | None = None,
        page_token: str | None = None,
        history_length: int | None = None,
        status_timestamp_after: str | None = None,
        include_artifacts: bool | None = None,
    ) -> ListTasksResponse:
        """List tasks for an agent (v1.0 only).

        Args:
            agent_name: Name of the agent.
            version: Agent deployment version.
            tenant: Tenant identifier.
            context_id: Filter by conversation context.
            status: Filter by task state.
            page_size: Results per page (1-100, default 50).
            page_token: Cursor from previous response.
            history_length: Max history messages per task.
            status_timestamp_after: ISO 8601 timestamp filter.
            include_artifacts: Whether to include artifacts.

        Returns:
            ListTasksResponse with tasks and pagination info.

        Raises:
            A2AError: If called with A2A v0.3 (not supported).
        """
        if self._a2a_version != A2A_V10:
            raise A2AError(
                "ListTasks is only available in A2A v1.0. "
                "Set a2a_version='1.0' when creating the client."
            )
        params: dict[str, Any] = {}
        if tenant is not None:
            params["tenant"] = tenant
        if context_id is not None:
            params["contextId"] = context_id
        if status is not None:
            state_str = status.value if isinstance(status, TaskState) else status
            params["status"] = _CANONICAL_TO_V1_STATE.get(state_str, state_str)
        if page_size is not None:
            params["pageSize"] = page_size
        if page_token is not None:
            params["pageToken"] = page_token
        if history_length is not None:
            params["historyLength"] = history_length
        if status_timestamp_after is not None:
            params["statusTimestampAfter"] = status_timestamp_after
        if include_artifacts is not None:
            params["includeArtifacts"] = include_artifacts

        path = f"{_a2a_path(agent_name, version)}/"
        envelope = build_request(self._method("list_tasks"), params)
        data = self._http.post(path, json=envelope, headers=self._headers())
        result = unwrap_response(data)
        return ListTasksResponse.model_validate(result)

    def subscribe_to_task(
        self,
        agent_name: str,
        *,
        task_id: str,
        version: int | None = None,
        tenant: str | None = None,
    ) -> A2AStream:
        """Subscribe to task updates via SSE stream.

        Monitors an existing task for status and artifact updates.
        The first event is the current Task state. The stream closes
        when the task reaches a terminal state.

        Args:
            agent_name: Name of the agent.
            task_id: Task identifier to subscribe to.
            version: Agent deployment version.
            tenant: Tenant identifier (v1.0 only).

        Returns:
            A2AStream yielding Task, TaskStatusUpdateEvent, and
            TaskArtifactUpdateEvent events.
        """
        from bud._a2a_streaming import A2AStream as A2AStreamCls

        params: dict[str, Any] = {"id": task_id}
        if tenant is not None:
            params["tenant"] = tenant

        path = f"{_a2a_path(agent_name, version)}/"
        envelope = build_request(self._method("subscribe_to_task"), params)
        response_ctx = self._http.stream(
            "POST", path, json=envelope, headers=self._headers()
        )
        response = response_ctx.__enter__()
        return A2AStreamCls(
            response,
            response_context=response_ctx,
            a2a_version=self._a2a_version,
        )

    def get_extended_agent_card(
        self,
        agent_name: str,
        *,
        version: int | None = None,
        tenant: str | None = None,
    ) -> AgentCard:
        """Get the extended (authenticated) agent card via JSON-RPC.

        Unlike ``get_agent_card()`` which performs a plain GET to
        ``.well-known/agent-card.json``, this makes an authenticated
        JSON-RPC call that may return additional capabilities.

        Args:
            agent_name: Name of the agent.
            version: Agent deployment version.
            tenant: Tenant identifier (v1.0 only).

        Returns:
            AgentCard with extended metadata.
        """
        params: dict[str, Any] = {}
        if tenant is not None:
            params["tenant"] = tenant
        path = f"{_a2a_path(agent_name, version)}/"
        envelope = build_request(self._method("get_card"), params or None)
        data = self._http.post(path, json=envelope, headers=self._headers())
        result = unwrap_response(data)
        return AgentCard.model_validate(result)


# ---------------------------------------------------------------------------
# Async resource
# ---------------------------------------------------------------------------


class AsyncA2A(AsyncResource):
    """Async A2A (Agent-to-Agent) protocol resource.

    Async version of A2A resource.
    """

    def __init__(
        self, http: AsyncHttpClient, a2a_version: str = A2A_DEFAULT_VERSION
    ) -> None:
        super().__init__(http)
        self._a2a_version = a2a_version

    @property
    def a2a_version(self) -> str:
        """Current A2A protocol version."""
        return self._a2a_version

    @a2a_version.setter
    def a2a_version(self, value: str) -> None:
        if value not in (A2A_V03, A2A_V10):
            raise ValueError(f"Unsupported A2A version: {value!r}. Use '0.3' or '1.0'.")
        self._a2a_version = value

    def _headers(self) -> dict[str, str]:
        return {"A2A-Version": self._a2a_version}

    def _method(self, key: str) -> str:
        return _METHOD_NAMES[self._a2a_version][key]

    async def get_agent_card(
        self,
        agent_name: str,
        *,
        version: int | None = None,
    ) -> AgentCard:
        """Discover an agent's capabilities via its Agent Card."""
        path = _agent_card_path(agent_name, version)
        data = await self._http.get(path, headers=self._headers())
        return AgentCard.model_validate(data)

    @overload
    async def send_message(
        self,
        agent_name: str,
        *,
        message: str | Message | dict[str, Any],
        stream: Literal[False] = False,
        version: int | None = None,
        context_id: str | None = None,
        task_id: str | None = None,
        configuration: SendMessageConfiguration | dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SendMessageResponse: ...

    @overload
    async def send_message(
        self,
        agent_name: str,
        *,
        message: str | Message | dict[str, Any],
        stream: Literal[True],
        version: int | None = None,
        context_id: str | None = None,
        task_id: str | None = None,
        configuration: SendMessageConfiguration | dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncA2AStream: ...

    async def send_message(
        self,
        agent_name: str,
        *,
        message: str | Message | dict[str, Any],
        stream: bool = False,
        version: int | None = None,
        context_id: str | None = None,
        task_id: str | None = None,
        configuration: SendMessageConfiguration | dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SendMessageResponse | AsyncA2AStream:
        """Send a message to an A2A agent (async)."""
        params = _build_message_params(
            message,
            context_id=context_id,
            task_id=task_id,
            configuration=configuration,
            metadata=metadata,
            a2a_version=self._a2a_version,
        )
        method = self._method("stream" if stream else "send")
        path = f"{_a2a_path(agent_name, version)}/"
        envelope = build_request(method, params)

        if stream:
            from bud._a2a_streaming import AsyncA2AStream as AsyncA2AStreamCls

            response_ctx = self._http.async_stream(
                "POST", path, json=envelope, headers=self._headers()
            )
            response = await response_ctx.__aenter__()
            return AsyncA2AStreamCls(
                response,
                response_context=response_ctx,
                a2a_version=self._a2a_version,
            )

        data = await self._http.post(path, json=envelope, headers=self._headers())
        result = unwrap_response(data)
        return _parse_send_response(result)

    async def get_task(
        self,
        agent_name: str,
        *,
        task_id: str,
        version: int | None = None,
        history_length: int | None = None,
        tenant: str | None = None,
    ) -> Task:
        """Get the state of an existing task (async)."""
        params: dict[str, Any] = {"id": task_id}
        if history_length is not None:
            params["historyLength"] = history_length
        if tenant is not None:
            params["tenant"] = tenant
        path = f"{_a2a_path(agent_name, version)}/"
        envelope = build_request(self._method("get_task"), params)
        data = await self._http.post(path, json=envelope, headers=self._headers())
        result = unwrap_response(data)
        return Task.model_validate(result)

    async def cancel_task(
        self,
        agent_name: str,
        *,
        task_id: str,
        version: int | None = None,
        tenant: str | None = None,
    ) -> Task:
        """Cancel a running task (async)."""
        params: dict[str, Any] = {"id": task_id}
        if tenant is not None:
            params["tenant"] = tenant
        path = f"{_a2a_path(agent_name, version)}/"
        envelope = build_request(self._method("cancel_task"), params)
        data = await self._http.post(path, json=envelope, headers=self._headers())
        result = unwrap_response(data)
        return Task.model_validate(result)

    async def list_tasks(
        self,
        agent_name: str,
        *,
        version: int | None = None,
        tenant: str | None = None,
        context_id: str | None = None,
        status: TaskState | str | None = None,
        page_size: int | None = None,
        page_token: str | None = None,
        history_length: int | None = None,
        status_timestamp_after: str | None = None,
        include_artifacts: bool | None = None,
    ) -> ListTasksResponse:
        """List tasks for an agent (v1.0 only, async)."""
        if self._a2a_version != A2A_V10:
            raise A2AError(
                "ListTasks is only available in A2A v1.0. "
                "Set a2a_version='1.0' when creating the client."
            )
        params: dict[str, Any] = {}
        if tenant is not None:
            params["tenant"] = tenant
        if context_id is not None:
            params["contextId"] = context_id
        if status is not None:
            state_str = status.value if isinstance(status, TaskState) else status
            params["status"] = _CANONICAL_TO_V1_STATE.get(state_str, state_str)
        if page_size is not None:
            params["pageSize"] = page_size
        if page_token is not None:
            params["pageToken"] = page_token
        if history_length is not None:
            params["historyLength"] = history_length
        if status_timestamp_after is not None:
            params["statusTimestampAfter"] = status_timestamp_after
        if include_artifacts is not None:
            params["includeArtifacts"] = include_artifacts

        path = f"{_a2a_path(agent_name, version)}/"
        envelope = build_request(self._method("list_tasks"), params)
        data = await self._http.post(path, json=envelope, headers=self._headers())
        result = unwrap_response(data)
        return ListTasksResponse.model_validate(result)

    async def subscribe_to_task(
        self,
        agent_name: str,
        *,
        task_id: str,
        version: int | None = None,
        tenant: str | None = None,
    ) -> AsyncA2AStream:
        """Subscribe to task updates via SSE stream (async)."""
        from bud._a2a_streaming import AsyncA2AStream as AsyncA2AStreamCls

        params: dict[str, Any] = {"id": task_id}
        if tenant is not None:
            params["tenant"] = tenant

        path = f"{_a2a_path(agent_name, version)}/"
        envelope = build_request(self._method("subscribe_to_task"), params)
        response_ctx = self._http.async_stream(
            "POST", path, json=envelope, headers=self._headers()
        )
        response = await response_ctx.__aenter__()
        return AsyncA2AStreamCls(
            response,
            response_context=response_ctx,
            a2a_version=self._a2a_version,
        )

    async def get_extended_agent_card(
        self,
        agent_name: str,
        *,
        version: int | None = None,
        tenant: str | None = None,
    ) -> AgentCard:
        """Get the extended (authenticated) agent card via JSON-RPC (async)."""
        params: dict[str, Any] = {}
        if tenant is not None:
            params["tenant"] = tenant
        path = f"{_a2a_path(agent_name, version)}/"
        envelope = build_request(self._method("get_card"), params or None)
        data = await self._http.post(path, json=envelope, headers=self._headers())
        result = unwrap_response(data)
        return AgentCard.model_validate(result)
