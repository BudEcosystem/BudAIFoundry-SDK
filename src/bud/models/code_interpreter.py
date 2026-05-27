"""Models for the code-interpreter custom-template + agent-tool surface.

Surfaces three types to SDK consumers:

* :class:`Template` — the templates row (builtin or custom). One model covers
  both kinds; the ``type`` field discriminates.
* :class:`NetworkPolicy` — input type for ``agents.add_code_interpreter``.
* :class:`AgentToolBinding` — the result of attaching a code-interpreter
  to an agent (a prompt version). Carries the auto-provisioned ``env_id``
  read-only for visibility.

The wire-format ``commands`` is a ``list[str]`` of raw Dockerfile
instructions. No DSL / op-list — see ``docs/api/code_interpreter.md`` for
the deny-list rules enforced server-side.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import ConfigDict, Field

from bud.models.common import BudModel

TemplateStatus = Literal["pending", "building", "ready", "failed"]


class NetworkPolicy(BudModel):
    """Per-environment network policy.

    Three modes:

    * ``type="disabled"`` — block all egress.
    * ``type="open"`` — unrestricted egress.
    * ``type="filtered"`` — caller-defined allow / deny lists.

    ``allow_out`` / ``deny_out`` accept IP literals, CIDR ranges, domain
    names, wildcard domains (``"*.example.com"``), and the case-insensitive
    sentinel ``"ALL_TRAFFIC"`` (which expands to ``0.0.0.0/0``).
    """

    type: Literal["disabled", "open", "filtered"] = "disabled"
    allow_out: list[str] = Field(default_factory=list)
    deny_out: list[str] = Field(default_factory=list)


class Template(BudModel):
    """A code-interpreter template row (builtin or custom).

    Returned by :meth:`bud.resources.code_interpreter.Templates.create`,
    ``.get``, and ``.update``. SDK callers typically only inspect ``id``,
    ``status``, and ``error_message`` (for failed builds) — the rest is
    informational. The ``commands`` field carries the verbatim Dockerfile
    instructions; it's empty for builtin templates.
    """

    # Allow extra fields so server-side additions don't break clients.
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        use_enum_values=True,
        extra="allow",
    )

    id: str
    type: str
    project_id: UUID | None = None
    status: TemplateStatus
    commands: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    cpu_count: int
    memory_mb: int
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AgentToolBinding(BudModel):
    """Result of ``agents.add_code_interpreter`` / ``agents.get_code_interpreter``.

    ``env_id`` is the auto-provisioned budcodeinterpreter environment id —
    surfaced for visibility / debugging only. SDK consumers do not address
    it back; the binding lifecycle (re-upsert, delete) goes through the
    ``agents.*`` methods.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        use_enum_values=True,
        extra="allow",
    )

    agent_id: str
    version: int
    tool_name: Literal["code_interpreter"] = "code_interpreter"
    env_id: str
    template_id: str | None = None
    custom_template_id: str | None = None
    config: dict[str, Any] | None = None


__all__ = [
    "Template",
    "NetworkPolicy",
    "AgentToolBinding",
    "TemplateStatus",
]
