"""Action models."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from bud.models.common import BudModel


class ActionParam(BudModel):
    """Action parameter definition."""

    name: str
    label: str | None = None
    type: str
    description: str | None = None
    required: bool = False
    default: Any = None
    placeholder: str | None = None
    options: list[dict[str, Any]] | None = None
    validation: dict[str, Any] | None = None


class Action(BudModel):
    """Action definition."""

    type: str
    name: str
    version: str | None = None
    description: str | None = None
    category: str | None = None
    icon: str | None = None
    color: str | None = None
    params: list[ActionParam] = Field(default_factory=list)
