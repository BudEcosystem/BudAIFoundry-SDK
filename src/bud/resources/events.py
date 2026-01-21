"""Event resource operations."""

from __future__ import annotations

import builtins
from typing import Any

from bud.models.event import Event, EventTrigger, EventType
from bud.resources._base import AsyncResource, SyncResource


class Events(SyncResource):
    """Event operations."""

    def list(
        self,
        *,
        event_type: EventType | str | None = None,
        source: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> builtins.list[Event]:
        """List events.

        Args:
            event_type: Filter by event type
            source: Filter by source
            page: Page number
            per_page: Items per page

        Returns:
            List of events
        """
        params: dict[str, Any] = {
            "page": page,
            "per_page": per_page,
        }
        if event_type:
            params["type"] = event_type.value if isinstance(event_type, EventType) else event_type
        if source:
            params["source"] = source

        data = self._http.get("/events", params=params)
        items = data.get("items", data) if isinstance(data, dict) else data
        return [Event.model_validate(item) for item in items]

    def get(self, event_id: str) -> Event:
        """Get an event by ID.

        Args:
            event_id: Event ID

        Returns:
            Event
        """
        data = self._http.get(f"/events/{event_id}")
        return Event.model_validate(data)

    # Event Triggers
    def create_trigger(
        self,
        pipeline_id: str,
        *,
        name: str,
        event_type: EventType | str,
        description: str = "",
        filter: dict[str, Any] | None = None,
    ) -> EventTrigger:
        """Create an event trigger.

        Args:
            pipeline_id: Pipeline to trigger
            name: Trigger name
            event_type: Event type to listen for
            description: Trigger description
            filter: Event filter criteria

        Returns:
            Created event trigger
        """
        data = self._http.post(
            "/event-triggers",
            json={
                "pipeline_id": pipeline_id,
                "name": name,
                "event_type": event_type.value if isinstance(event_type, EventType) else event_type,
                "description": description,
                "filter": filter or {},
            },
        )
        return EventTrigger.model_validate(data)

    def list_triggers(
        self,
        *,
        pipeline_id: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> builtins.list[EventTrigger]:
        """List event triggers.

        Args:
            pipeline_id: Filter by pipeline ID
            page: Page number
            per_page: Items per page

        Returns:
            List of event triggers
        """
        params: dict[str, Any] = {
            "page": page,
            "per_page": per_page,
        }
        if pipeline_id:
            params["pipeline_id"] = pipeline_id

        data = self._http.get("/event-triggers", params=params)
        items = data.get("items", data) if isinstance(data, dict) else data
        return [EventTrigger.model_validate(item) for item in items]

    def get_trigger(self, trigger_id: str) -> EventTrigger:
        """Get an event trigger by ID.

        Args:
            trigger_id: Trigger ID

        Returns:
            Event trigger
        """
        data = self._http.get(f"/event-triggers/{trigger_id}")
        return EventTrigger.model_validate(data)

    def delete_trigger(self, trigger_id: str) -> None:
        """Delete an event trigger.

        Args:
            trigger_id: Trigger ID
        """
        self._http.delete(f"/event-triggers/{trigger_id}")


class AsyncEvents(AsyncResource):
    """Async event operations."""

    async def list(
        self,
        *,
        event_type: EventType | str | None = None,
        source: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> builtins.list[Event]:
        """List events."""
        params: dict[str, Any] = {
            "page": page,
            "per_page": per_page,
        }
        if event_type:
            params["type"] = event_type.value if isinstance(event_type, EventType) else event_type
        if source:
            params["source"] = source

        data = await self._http.get("/events", params=params)
        items = data.get("items", data) if isinstance(data, dict) else data
        return [Event.model_validate(item) for item in items]

    async def get(self, event_id: str) -> Event:
        """Get an event by ID."""
        data = await self._http.get(f"/events/{event_id}")
        return Event.model_validate(data)

    async def create_trigger(
        self,
        pipeline_id: str,
        *,
        name: str,
        event_type: EventType | str,
        description: str = "",
        filter: dict[str, Any] | None = None,
    ) -> EventTrigger:
        """Create an event trigger."""
        data = await self._http.post(
            "/event-triggers",
            json={
                "pipeline_id": pipeline_id,
                "name": name,
                "event_type": event_type.value if isinstance(event_type, EventType) else event_type,
                "description": description,
                "filter": filter or {},
            },
        )
        return EventTrigger.model_validate(data)

    async def list_triggers(
        self,
        *,
        pipeline_id: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> builtins.list[EventTrigger]:
        """List event triggers."""
        params: dict[str, Any] = {
            "page": page,
            "per_page": per_page,
        }
        if pipeline_id:
            params["pipeline_id"] = pipeline_id

        data = await self._http.get("/event-triggers", params=params)
        items = data.get("items", data) if isinstance(data, dict) else data
        return [EventTrigger.model_validate(item) for item in items]

    async def get_trigger(self, trigger_id: str) -> EventTrigger:
        """Get an event trigger by ID."""
        data = await self._http.get(f"/event-triggers/{trigger_id}")
        return EventTrigger.model_validate(data)

    async def delete_trigger(self, trigger_id: str) -> None:
        """Delete an event trigger."""
        await self._http.delete(f"/event-triggers/{trigger_id}")
