"""Schedule resource operations."""

from __future__ import annotations

from typing import Any

from bud.models.execution import Execution
from bud.models.schedule import Schedule, ScheduleStatus
from bud.resources._base import AsyncResource, SyncResource


class Schedules(SyncResource):
    """Schedule operations."""

    def create(
        self,
        pipeline_id: str,
        *,
        name: str,
        cron: str,
        description: str = "",
        timezone: str = "UTC",
        params: dict[str, Any] | None = None,
    ) -> Schedule:
        """Create a new schedule.

        Args:
            pipeline_id: Pipeline ID to schedule
            name: Schedule name
            cron: Cron expression
            description: Schedule description
            timezone: Timezone for cron
            params: Default execution parameters

        Returns:
            Created schedule
        """
        data = self._http.post(
            "/budpipeline/schedules",
            json={
                "pipeline_id": pipeline_id,
                "name": name,
                "cron": cron,
                "description": description,
                "timezone": timezone,
                "params": params or {},
            },
        )
        return Schedule.model_validate(data)

    def list(
        self,
        *,
        pipeline_id: str | None = None,
        status: ScheduleStatus | str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> list[Schedule]:
        """List schedules.

        Args:
            pipeline_id: Filter by pipeline ID
            status: Filter by status
            page: Page number
            per_page: Items per page

        Returns:
            List of schedules
        """
        params: dict[str, Any] = {
            "page": page,
            "per_page": per_page,
        }
        if pipeline_id:
            params["pipeline_id"] = pipeline_id
        if status:
            params["status"] = status.value if isinstance(status, ScheduleStatus) else status

        data = self._http.get("/budpipeline/schedules", params=params)
        items = data.get("items", data) if isinstance(data, dict) else data
        return [Schedule.model_validate(item) for item in items]

    def get(self, schedule_id: str) -> Schedule:
        """Get a schedule by ID.

        Args:
            schedule_id: Schedule ID

        Returns:
            Schedule
        """
        data = self._http.get(f"/budpipeline/schedules/{schedule_id}")
        return Schedule.model_validate(data)

    def update(
        self,
        schedule_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        cron: str | None = None,
        timezone: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> Schedule:
        """Update a schedule.

        Args:
            schedule_id: Schedule ID
            name: New name
            description: New description
            cron: New cron expression
            timezone: New timezone
            params: New parameters

        Returns:
            Updated schedule
        """
        update_data = {}
        if name is not None:
            update_data["name"] = name
        if description is not None:
            update_data["description"] = description
        if cron is not None:
            update_data["cron"] = cron
        if timezone is not None:
            update_data["timezone"] = timezone
        if params is not None:
            update_data["params"] = params

        data = self._http.patch(f"/budpipeline/schedules/{schedule_id}", json=update_data)
        return Schedule.model_validate(data)

    def delete(self, schedule_id: str) -> None:
        """Delete a schedule.

        Args:
            schedule_id: Schedule ID
        """
        self._http.delete(f"/budpipeline/schedules/{schedule_id}")

    def pause(self, schedule_id: str) -> Schedule:
        """Pause a schedule.

        Args:
            schedule_id: Schedule ID

        Returns:
            Paused schedule
        """
        data = self._http.post(f"/budpipeline/schedules/{schedule_id}/pause", json={})
        return Schedule.model_validate(data)

    def resume(self, schedule_id: str) -> Schedule:
        """Resume a paused schedule.

        Args:
            schedule_id: Schedule ID

        Returns:
            Resumed schedule
        """
        data = self._http.post(f"/budpipeline/schedules/{schedule_id}/resume", json={})
        return Schedule.model_validate(data)

    def trigger(self, schedule_id: str) -> Execution:
        """Manually trigger a schedule.

        Args:
            schedule_id: Schedule ID

        Returns:
            Created execution
        """
        data = self._http.post(f"/budpipeline/schedules/{schedule_id}/trigger", json={})
        return Execution.model_validate(data)


class AsyncSchedules(AsyncResource):
    """Async schedule operations."""

    async def create(
        self,
        pipeline_id: str,
        *,
        name: str,
        cron: str,
        description: str = "",
        timezone: str = "UTC",
        params: dict[str, Any] | None = None,
    ) -> Schedule:
        """Create a new schedule."""
        data = await self._http.post(
            "/budpipeline/schedules",
            json={
                "pipeline_id": pipeline_id,
                "name": name,
                "cron": cron,
                "description": description,
                "timezone": timezone,
                "params": params or {},
            },
        )
        return Schedule.model_validate(data)

    async def list(
        self,
        *,
        pipeline_id: str | None = None,
        status: ScheduleStatus | str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> list[Schedule]:
        """List schedules."""
        params: dict[str, Any] = {
            "page": page,
            "per_page": per_page,
        }
        if pipeline_id:
            params["pipeline_id"] = pipeline_id
        if status:
            params["status"] = status.value if isinstance(status, ScheduleStatus) else status

        data = await self._http.get("/budpipeline/schedules", params=params)
        items = data.get("items", data) if isinstance(data, dict) else data
        return [Schedule.model_validate(item) for item in items]

    async def get(self, schedule_id: str) -> Schedule:
        """Get a schedule by ID."""
        data = await self._http.get(f"/budpipeline/schedules/{schedule_id}")
        return Schedule.model_validate(data)

    async def update(
        self,
        schedule_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        cron: str | None = None,
        timezone: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> Schedule:
        """Update a schedule."""
        update_data = {}
        if name is not None:
            update_data["name"] = name
        if description is not None:
            update_data["description"] = description
        if cron is not None:
            update_data["cron"] = cron
        if timezone is not None:
            update_data["timezone"] = timezone
        if params is not None:
            update_data["params"] = params

        data = await self._http.patch(f"/budpipeline/schedules/{schedule_id}", json=update_data)
        return Schedule.model_validate(data)

    async def delete(self, schedule_id: str) -> None:
        """Delete a schedule."""
        await self._http.delete(f"/budpipeline/schedules/{schedule_id}")

    async def pause(self, schedule_id: str) -> Schedule:
        """Pause a schedule."""
        data = await self._http.post(f"/budpipeline/schedules/{schedule_id}/pause", json={})
        return Schedule.model_validate(data)

    async def resume(self, schedule_id: str) -> Schedule:
        """Resume a paused schedule."""
        data = await self._http.post(f"/budpipeline/schedules/{schedule_id}/resume", json={})
        return Schedule.model_validate(data)

    async def trigger(self, schedule_id: str) -> Execution:
        """Manually trigger a schedule."""
        data = await self._http.post(f"/budpipeline/schedules/{schedule_id}/trigger", json={})
        return Execution.model_validate(data)
