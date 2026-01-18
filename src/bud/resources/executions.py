"""Execution resource operations."""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

from bud.exceptions import ExecutionError
from bud.models.execution import (
    Execution,
    ExecutionEvent,
    ExecutionProgress,
    ExecutionStatus,
    ExecutionStep,
)
from bud.resources._base import AsyncResource, SyncResource


class Executions(SyncResource):
    """Execution operations."""

    def create(
        self,
        pipeline_id: str,
        *,
        params: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        wait: bool = False,
        poll_interval: float = 2.0,
        timeout: float | None = None,
    ) -> Execution:
        """Create/trigger a pipeline execution.

        Args:
            pipeline_id: Pipeline ID to execute
            params: Execution parameters
            context: Execution context
            wait: Wait for execution to complete
            poll_interval: Polling interval in seconds (when wait=True)
            timeout: Maximum wait time in seconds

        Returns:
            Execution object

        Raises:
            ExecutionError: If execution fails (when wait=True)
            TimeoutError: If timeout exceeded (when wait=True)
        """
        data = self._http.post(
            f"/budpipeline/{pipeline_id}/execute",
            json={
                "params": params or {},
                "context": context or {},
            },
        )
        execution = Execution.model_validate(data)

        if wait:
            execution = self._wait_for_completion(
                execution.effective_id,
                poll_interval=poll_interval,
                timeout=timeout,
            )

        return execution

    def run(
        self,
        pipeline_id: str,
        *,
        params: dict[str, Any] | None = None,
        wait: bool = True,
        timeout: float | None = None,
    ) -> Execution:
        """Convenience method to run a pipeline and wait for completion.

        Args:
            pipeline_id: Pipeline ID to execute
            params: Execution parameters
            wait: Wait for completion (default True)
            timeout: Maximum wait time

        Returns:
            Completed execution
        """
        return self.create(
            pipeline_id,
            params=params,
            wait=wait,
            timeout=timeout,
        )

    def list(
        self,
        *,
        pipeline_id: str | None = None,
        status: ExecutionStatus | str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> list[Execution]:
        """List executions.

        Args:
            pipeline_id: Filter by pipeline ID
            status: Filter by status
            page: Page number
            per_page: Items per page

        Returns:
            List of executions
        """
        params: dict[str, Any] = {
            "page": page,
            "per_page": per_page,
        }
        if pipeline_id:
            params["pipeline_id"] = pipeline_id
        if status:
            params["status"] = status.value if isinstance(status, ExecutionStatus) else status

        data = self._http.get("/budpipeline/executions", params=params)
        # API returns 'executions' key, fall back to 'items' for compatibility
        if isinstance(data, dict):
            items = data.get("executions", data.get("items", data))
        else:
            items = data
        return [Execution.model_validate(item) for item in items]

    def get(self, execution_id: str) -> Execution:
        """Get an execution by ID.

        Args:
            execution_id: Execution ID

        Returns:
            Execution
        """
        data = self._http.get(f"/budpipeline/executions/{execution_id}")
        return Execution.model_validate(data)

    def cancel(self, execution_id: str) -> Execution:
        """Cancel a running execution.

        Args:
            execution_id: Execution ID

        Returns:
            Cancelled execution
        """
        data = self._http.post(f"/budpipeline/executions/{execution_id}/cancel", json={})
        return Execution.model_validate(data)

    def retry(self, execution_id: str) -> Execution:
        """Retry a failed execution.

        Args:
            execution_id: Execution ID

        Returns:
            New execution
        """
        data = self._http.post(f"/budpipeline/executions/{execution_id}/retry", json={})
        return Execution.model_validate(data)

    def get_progress(self, execution_id: str) -> ExecutionProgress:
        """Get execution progress.

        Args:
            execution_id: Execution ID

        Returns:
            Execution progress
        """
        data = self._http.get(f"/budpipeline/executions/{execution_id}/progress")
        return ExecutionProgress.model_validate(data)

    def get_steps(self, execution_id: str) -> list[ExecutionStep]:
        """Get execution steps.

        Args:
            execution_id: Execution ID

        Returns:
            List of execution steps
        """
        data = self._http.get(f"/budpipeline/executions/{execution_id}/steps")
        items = data.get("items", data) if isinstance(data, dict) else data
        return [ExecutionStep.model_validate(item) for item in items]

    def get_events(
        self,
        execution_id: str,
        *,
        step_id: str | None = None,
    ) -> list[ExecutionEvent]:
        """Get execution events.

        Args:
            execution_id: Execution ID
            step_id: Filter by step ID

        Returns:
            List of execution events (may be empty if API doesn't support events)
        """
        params = {}
        if step_id:
            params["step_id"] = step_id

        try:
            data = self._http.get(
                f"/budpipeline/executions/{execution_id}/events", params=params or None
            )
            items = data.get("items", data) if isinstance(data, dict) else data
            return [ExecutionEvent.model_validate(item) for item in items]
        except Exception:
            # Events endpoint may not exist in this API version
            return []

    def stream_events(
        self,
        execution_id: str,
        *,
        poll_interval: float = 1.0,
    ) -> Iterator[ExecutionEvent]:
        """Stream execution events.

        Args:
            execution_id: Execution ID
            poll_interval: Polling interval in seconds

        Yields:
            Execution events
        """
        seen_ids: set[str] = set()

        while True:
            execution = self.get(execution_id)
            events = self.get_events(execution_id)

            for event in events:
                if event.id not in seen_ids:
                    seen_ids.add(event.id)
                    yield event

            if execution.status in (
                ExecutionStatus.COMPLETED,
                ExecutionStatus.FAILED,
                ExecutionStatus.CANCELLED,
                ExecutionStatus.TIMED_OUT,
            ):
                break

            time.sleep(poll_interval)

    def _wait_for_completion(
        self,
        execution_id: str,
        *,
        poll_interval: float = 2.0,
        timeout: float | None = None,
    ) -> Execution:
        """Wait for execution to complete."""
        start_time = time.time()

        while True:
            execution = self.get(execution_id)

            if execution.status == ExecutionStatus.COMPLETED:
                return execution

            if execution.status in (
                ExecutionStatus.FAILED,
                ExecutionStatus.CANCELLED,
                ExecutionStatus.TIMED_OUT,
            ):
                raise ExecutionError(
                    f"Execution {execution.status.value}: {execution.error or 'Unknown error'}",
                    execution_id=execution_id,
                    status=execution.status.value,
                )

            if timeout and (time.time() - start_time) > timeout:
                raise TimeoutError(f"Execution timed out after {timeout}s")

            time.sleep(poll_interval)


class AsyncExecutions(AsyncResource):
    """Async execution operations."""

    async def create(
        self,
        pipeline_id: str,
        *,
        params: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        wait: bool = False,
        poll_interval: float = 2.0,
        timeout: float | None = None,
    ) -> Execution:
        """Create/trigger a pipeline execution."""
        data = await self._http.post(
            f"/budpipeline/{pipeline_id}/execute",
            json={
                "params": params or {},
                "context": context or {},
            },
        )
        execution = Execution.model_validate(data)

        if wait:
            execution = await self._wait_for_completion(
                execution.effective_id,
                poll_interval=poll_interval,
                timeout=timeout,
            )

        return execution

    async def run(
        self,
        pipeline_id: str,
        *,
        params: dict[str, Any] | None = None,
        wait: bool = True,
        timeout: float | None = None,
    ) -> Execution:
        """Convenience method to run a pipeline and wait for completion."""
        return await self.create(
            pipeline_id,
            params=params,
            wait=wait,
            timeout=timeout,
        )

    async def list(
        self,
        *,
        pipeline_id: str | None = None,
        status: ExecutionStatus | str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> list[Execution]:
        """List executions."""
        params: dict[str, Any] = {
            "page": page,
            "per_page": per_page,
        }
        if pipeline_id:
            params["pipeline_id"] = pipeline_id
        if status:
            params["status"] = status.value if isinstance(status, ExecutionStatus) else status

        data = await self._http.get("/budpipeline/executions", params=params)
        items = data.get("items", data) if isinstance(data, dict) else data
        return [Execution.model_validate(item) for item in items]

    async def get(self, execution_id: str) -> Execution:
        """Get an execution by ID."""
        data = await self._http.get(f"/budpipeline/executions/{execution_id}")
        return Execution.model_validate(data)

    async def cancel(self, execution_id: str) -> Execution:
        """Cancel a running execution."""
        data = await self._http.post(f"/budpipeline/executions/{execution_id}/cancel", json={})
        return Execution.model_validate(data)

    async def retry(self, execution_id: str) -> Execution:
        """Retry a failed execution."""
        data = await self._http.post(f"/budpipeline/executions/{execution_id}/retry", json={})
        return Execution.model_validate(data)

    async def get_progress(self, execution_id: str) -> ExecutionProgress:
        """Get execution progress."""
        data = await self._http.get(f"/budpipeline/executions/{execution_id}/progress")
        return ExecutionProgress.model_validate(data)

    async def get_steps(self, execution_id: str) -> list[ExecutionStep]:
        """Get execution steps."""
        data = await self._http.get(f"/budpipeline/executions/{execution_id}/steps")
        items = data.get("items", data) if isinstance(data, dict) else data
        return [ExecutionStep.model_validate(item) for item in items]

    async def get_events(
        self,
        execution_id: str,
        *,
        step_id: str | None = None,
    ) -> list[ExecutionEvent]:
        """Get execution events."""
        params = {}
        if step_id:
            params["step_id"] = step_id

        data = await self._http.get(
            f"/budpipeline/executions/{execution_id}/events", params=params or None
        )
        items = data.get("items", data) if isinstance(data, dict) else data
        return [ExecutionEvent.model_validate(item) for item in items]

    async def _wait_for_completion(
        self,
        execution_id: str,
        *,
        poll_interval: float = 2.0,
        timeout: float | None = None,
    ) -> Execution:
        """Wait for execution to complete."""
        import anyio

        start_time = time.time()

        while True:
            execution = await self.get(execution_id)

            if execution.status == ExecutionStatus.COMPLETED:
                return execution

            if execution.status in (
                ExecutionStatus.FAILED,
                ExecutionStatus.CANCELLED,
                ExecutionStatus.TIMED_OUT,
            ):
                raise ExecutionError(
                    f"Execution {execution.status.value}: {execution.error or 'Unknown error'}",
                    execution_id=execution_id,
                    status=execution.status.value,
                )

            if timeout and (time.time() - start_time) > timeout:
                raise TimeoutError(f"Execution timed out after {timeout}s")

            await anyio.sleep(poll_interval)
