"""A2A (Agent-to-Agent) protocol models.

Supports both A2A v0.3 and v1.0 wire formats. Models accept either format
on deserialization and normalize to a version-agnostic internal representation.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import ConfigDict, Field, field_validator, model_validator

from bud.models.common import BudModel

# ---------------------------------------------------------------------------
# v1.0 → canonical normalization maps
# ---------------------------------------------------------------------------

_V1_TASK_STATE_MAP: dict[str, str] = {
    "TASK_STATE_SUBMITTED": "submitted",
    "TASK_STATE_WORKING": "working",
    "TASK_STATE_INPUT_REQUIRED": "input-required",
    "TASK_STATE_COMPLETED": "completed",
    "TASK_STATE_FAILED": "failed",
    "TASK_STATE_CANCELED": "canceled",
    "TASK_STATE_REJECTED": "rejected",
    "TASK_STATE_AUTH_REQUIRED": "auth-required",
    "TASK_STATE_UNSPECIFIED": "unknown",
}

_V1_ROLE_MAP: dict[str, str] = {
    "ROLE_USER": "user",
    "ROLE_AGENT": "agent",
    "ROLE_UNSPECIFIED": "user",
}


def _normalize_task_state(v: Any) -> Any:
    """Normalize v1.0 SCREAMING_SNAKE task state to canonical lowercase."""
    if isinstance(v, str) and v in _V1_TASK_STATE_MAP:
        return _V1_TASK_STATE_MAP[v]
    return v


def _normalize_role(v: Any) -> Any:
    """Normalize v1.0 ROLE_USER/ROLE_AGENT to canonical lowercase."""
    if isinstance(v, str) and v in _V1_ROLE_MAP:
        return _V1_ROLE_MAP[v]
    return v


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TaskState(str, Enum):
    """A2A task lifecycle states."""

    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    REJECTED = "rejected"
    AUTH_REQUIRED = "auth-required"
    UNKNOWN = "unknown"


class Role(str, Enum):
    """A2A message sender role."""

    USER = "user"
    AGENT = "agent"


# ---------------------------------------------------------------------------
# Part (unified: accepts both v0.3 kind-based and v1.0 member-based formats)
# ---------------------------------------------------------------------------


class Part(BudModel):
    """A2A message part.

    Accepts both v0.3 format (``kind`` discriminator) and v1.0 format
    (member-presence discriminator). Normalizes to v1.0 canonical fields.
    """

    model_config = ConfigDict(extra="allow")

    # v1.0 content fields (oneOf)
    text: str | None = None
    raw: str | None = None  # base64-encoded bytes
    url: str | None = None
    data: dict[str, Any] | None = None

    # Common metadata
    metadata: dict[str, Any] | None = None
    filename: str | None = None
    media_type: str | None = Field(default=None, alias="mediaType")

    @model_validator(mode="before")
    @classmethod
    def _normalize_v03(cls, values: Any) -> Any:
        """Normalize v0.3 kind-based Part format to v1.0 canonical format."""
        if not isinstance(values, dict) or "kind" not in values:
            return values
        kind = values["kind"]
        if kind == "text":
            result: dict[str, Any] = {"text": values.get("text")}
            if values.get("metadata"):
                result["metadata"] = values["metadata"]
            return result
        if kind == "file":
            file_data = values.get("file", {})
            return {
                "raw": file_data.get("bytes") or file_data.get("fileWithBytes"),
                "url": file_data.get("uri") or file_data.get("fileWithUri"),
                "filename": file_data.get("name"),
                "mediaType": file_data.get("mimeType"),
                "metadata": values.get("metadata"),
            }
        if kind == "data":
            result = {"data": values.get("data")}
            if values.get("metadata"):
                result["metadata"] = values["metadata"]
            return result
        return values


# ---------------------------------------------------------------------------
# Core message types
# ---------------------------------------------------------------------------


class Message(BudModel):
    """A2A protocol message."""

    model_config = ConfigDict(extra="allow")

    message_id: str | None = Field(default=None, alias="messageId")
    role: Role
    parts: list[Part]
    context_id: str | None = Field(default=None, alias="contextId")
    task_id: str | None = Field(default=None, alias="taskId")
    reference_task_ids: list[str] | None = Field(default=None, alias="referenceTaskIds")
    metadata: dict[str, Any] | None = None
    extensions: list[str] | None = None

    @field_validator("role", mode="before")
    @classmethod
    def _normalize_role(cls, v: Any) -> Any:
        return _normalize_role(v)


class TaskStatus(BudModel):
    """Current status of an A2A task."""

    state: TaskState
    message: Message | None = None
    timestamp: str | None = None

    @field_validator("state", mode="before")
    @classmethod
    def _normalize_state(cls, v: Any) -> Any:
        return _normalize_task_state(v)


class Artifact(BudModel):
    """Output artifact from an A2A agent."""

    model_config = ConfigDict(extra="allow")

    artifact_id: str | None = Field(default=None, alias="artifactId")
    name: str | None = None
    description: str | None = None
    parts: list[Part]
    metadata: dict[str, Any] | None = None
    extensions: list[str] | None = None


# ---------------------------------------------------------------------------
# Task and response types
# ---------------------------------------------------------------------------


class Task(BudModel):
    """A2A task — the primary unit of tracked work."""

    model_config = ConfigDict(extra="allow")

    id: str
    context_id: str | None = Field(default=None, alias="contextId")
    status: TaskStatus
    artifacts: list[Artifact] | None = None
    history: list[Message] | None = None
    metadata: dict[str, Any] | None = None


class TaskStatusUpdateEvent(BudModel):
    """Streaming event: task status transition."""

    task_id: str = Field(alias="taskId")
    context_id: str | None = Field(default=None, alias="contextId")
    status: TaskStatus
    final: bool | None = None  # v0.3 only; removed in v1.0
    metadata: dict[str, Any] | None = None


class TaskArtifactUpdateEvent(BudModel):
    """Streaming event: artifact chunk."""

    task_id: str = Field(alias="taskId")
    context_id: str | None = Field(default=None, alias="contextId")
    artifact: Artifact
    append: bool | None = None
    last_chunk: bool | None = Field(default=None, alias="lastChunk")
    metadata: dict[str, Any] | None = None


class SendMessageConfiguration(BudModel):
    """Configuration for send_message requests."""

    model_config = ConfigDict(extra="allow")

    accepted_output_modes: list[str] | None = Field(
        default=None, alias="acceptedOutputModes"
    )
    history_length: int | None = Field(default=None, alias="historyLength")
    blocking: bool | None = None  # v0.3
    return_immediately: bool | None = Field(default=None, alias="returnImmediately")  # v1.0


class SendMessageResponse(BudModel):
    """Response from send_message. Contains either a task or a message."""

    task: Task | None = None
    message: Message | None = None


class ListTasksResponse(BudModel):
    """Paginated list of tasks (v1.0 only)."""

    tasks: list[Task]
    next_page_token: str = Field(default="", alias="nextPageToken")
    page_size: int = Field(default=0, alias="pageSize")
    total_size: int = Field(default=0, alias="totalSize")


# Type alias for streaming events
A2AStreamEvent = Task | Message | TaskStatusUpdateEvent | TaskArtifactUpdateEvent


# ---------------------------------------------------------------------------
# Agent Card types
# ---------------------------------------------------------------------------


class AgentProvider(BudModel):
    """Agent provider organization."""

    organization: str
    url: str


class AgentInterface(BudModel):
    """Supported protocol interface (v1.0)."""

    model_config = ConfigDict(extra="allow")

    url: str
    protocol_binding: str | None = Field(default=None, alias="protocolBinding")
    protocol_version: str | None = Field(default=None, alias="protocolVersion")
    tenant: str | None = None


class AgentCapabilities(BudModel):
    """Agent capability flags."""

    model_config = ConfigDict(extra="allow")

    streaming: bool = False
    push_notifications: bool = Field(default=False, alias="pushNotifications")
    state_transition_history: bool = Field(default=False, alias="stateTransitionHistory")
    extended_agent_card: bool = Field(default=False, alias="extendedAgentCard")


class AgentSkill(BudModel):
    """A skill/capability that an agent advertises."""

    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    description: str | None = None
    tags: list[str] | None = None
    examples: list[str] | None = None
    input_modes: list[str] | None = Field(default=None, alias="inputModes")
    output_modes: list[str] | None = Field(default=None, alias="outputModes")


class AgentCard(BudModel):
    """A2A agent card — metadata for discovery.

    Accepts both v0.3 (top-level ``url``, ``protocolVersion``) and v1.0
    (``supportedInterfaces`` array) formats.
    """

    model_config = ConfigDict(extra="allow")

    name: str
    description: str | None = None
    version: str | None = None

    # v0.3 fields
    url: str | None = None
    protocol_version: str | None = Field(default=None, alias="protocolVersion")

    # v1.0 fields
    supported_interfaces: list[AgentInterface] | None = Field(
        default=None, alias="supportedInterfaces"
    )

    # Common fields
    capabilities: AgentCapabilities | None = None
    skills: list[AgentSkill] | None = None
    default_input_modes: list[str] | None = Field(default=None, alias="defaultInputModes")
    default_output_modes: list[str] | None = Field(default=None, alias="defaultOutputModes")
    security_schemes: dict[str, Any] | None = Field(default=None, alias="securitySchemes")
    provider: AgentProvider | None = None
    icon_url: str | None = Field(default=None, alias="iconUrl")
    documentation_url: str | None = Field(default=None, alias="documentationUrl")
