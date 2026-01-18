"""Action resource operations."""

from __future__ import annotations

from bud.models.action import Action
from bud.resources._base import AsyncResource, SyncResource


class Actions(SyncResource):
    """Action operations."""

    def list(self) -> list[Action]:
        """List available actions.

        Returns:
            List of actions
        """
        data = self._http.get("/budpipeline/actions")
        items = data.get("actions", data) if isinstance(data, dict) else data
        return [Action.model_validate(item) for item in items]

    def get(self, action_type: str) -> Action:
        """Get an action by type.

        Args:
            action_type: Action type (e.g., "aggregate", "llm_call")

        Returns:
            Action
        """
        data = self._http.get(f"/budpipeline/actions/{action_type}")
        return Action.model_validate(data)


class AsyncActions(AsyncResource):
    """Async action operations."""

    async def list(self) -> list[Action]:
        """List available actions."""
        data = await self._http.get("/budpipeline/actions")
        items = data.get("actions", data) if isinstance(data, dict) else data
        return [Action.model_validate(item) for item in items]

    async def get(self, action_type: str) -> Action:
        """Get an action by type."""
        data = await self._http.get(f"/budpipeline/actions/{action_type}")
        return Action.model_validate(data)
