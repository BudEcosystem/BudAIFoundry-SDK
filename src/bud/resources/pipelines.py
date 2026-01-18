"""Pipeline resource operations."""

from __future__ import annotations

from typing import Any

from bud.models.pipeline import Pipeline, PipelineDAG, ValidationResult
from bud.resources._base import AsyncResource, SyncResource


class Pipelines(SyncResource):
    """Pipeline operations."""

    def create(
        self,
        dag: dict[str, Any] | PipelineDAG,
        *,
        name: str,
        description: str = "",
        tags: dict[str, str] | None = None,
    ) -> Pipeline:
        """Create a new pipeline.

        Args:
            dag: Pipeline DAG definition
            name: Pipeline name
            description: Pipeline description
            tags: Optional tags

        Returns:
            Created pipeline
        """
        if isinstance(dag, PipelineDAG):
            dag = dag.model_dump()

        # Convert to steps format expected by API
        api_dag = self._convert_dag_for_validation(dag)

        data = self._http.post(
            "/budpipeline",
            json={
                "name": name,
                "description": description,
                "dag": api_dag,
                "tags": tags or {},
            },
        )
        return Pipeline.model_validate(data)

    def list(
        self,
        *,
        include_system: bool = False,
        page: int = 1,
        per_page: int = 20,
    ) -> list[Pipeline]:
        """List pipelines.

        Args:
            include_system: Include system pipelines
            page: Page number
            per_page: Items per page

        Returns:
            List of pipelines
        """
        data = self._http.get(
            "/budpipeline",
            params={
                "include_system": include_system,
                "page": page,
                "per_page": per_page,
            },
        )
        items = data.get("items", data) if isinstance(data, dict) else data
        return [Pipeline.model_validate(item) for item in items]

    def get(self, pipeline_id: str) -> Pipeline:
        """Get a pipeline by ID.

        Args:
            pipeline_id: Pipeline ID

        Returns:
            Pipeline
        """
        data = self._http.get(f"/budpipeline/{pipeline_id}")
        return Pipeline.model_validate(data)

    def update(
        self,
        pipeline_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        dag: dict[str, Any] | None = None,
        is_active: bool | None = None,
        tags: dict[str, str] | None = None,
    ) -> Pipeline:
        """Update a pipeline.

        Args:
            pipeline_id: Pipeline ID
            name: New name
            description: New description
            dag: New DAG
            is_active: Active status
            tags: New tags

        Returns:
            Updated pipeline
        """
        update_data = {}
        if name is not None:
            update_data["name"] = name
        if description is not None:
            update_data["description"] = description
        if dag is not None:
            update_data["dag"] = dag
        if is_active is not None:
            update_data["is_active"] = is_active
        if tags is not None:
            update_data["tags"] = tags

        data = self._http.patch(f"/budpipeline/{pipeline_id}", json=update_data)
        return Pipeline.model_validate(data)

    def delete(self, pipeline_id: str) -> None:
        """Delete a pipeline.

        Args:
            pipeline_id: Pipeline ID
        """
        self._http.delete(f"/budpipeline/{pipeline_id}")

    def validate(self, dag: dict[str, Any]) -> ValidationResult:
        """Validate a pipeline DAG.

        Args:
            dag: Pipeline DAG to validate

        Returns:
            Validation result
        """
        # Convert nodes format to steps format expected by validation API
        api_dag = self._convert_dag_for_validation(dag)
        data = self._http.post("/budpipeline/validate", json={"dag": api_dag})
        return ValidationResult.model_validate(data)

    def _convert_dag_for_validation(self, dag: dict[str, Any]) -> dict[str, Any]:
        """Convert DAG from DSL format to API validation format."""
        # API validation expects "steps" not "nodes"
        nodes = dag.get("nodes", [])
        metadata = dag.get("metadata", {})

        steps = []
        for node in nodes:
            steps.append({
                "id": node.get("id"),
                "name": node.get("name", node.get("id")),
                "action": node.get("action_id", ""),
                "config": node.get("config", {}),
                "depends_on": node.get("depends_on", []),
            })

        return {
            "name": metadata.get("name", "unnamed-pipeline"),
            "steps": steps,
            "edges": dag.get("edges", []),
        }


class AsyncPipelines(AsyncResource):
    """Async pipeline operations."""

    async def create(
        self,
        dag: dict[str, Any] | PipelineDAG,
        *,
        name: str,
        description: str = "",
        tags: dict[str, str] | None = None,
    ) -> Pipeline:
        """Create a new pipeline."""
        if isinstance(dag, PipelineDAG):
            dag = dag.model_dump()

        # Convert to steps format expected by API
        api_dag = self._convert_dag_for_validation(dag)

        data = await self._http.post(
            "/budpipeline",
            json={
                "name": name,
                "description": description,
                "dag": api_dag,
                "tags": tags or {},
            },
        )
        return Pipeline.model_validate(data)

    async def list(
        self,
        *,
        include_system: bool = False,
        page: int = 1,
        per_page: int = 20,
    ) -> list[Pipeline]:
        """List pipelines."""
        data = await self._http.get(
            "/budpipeline",
            params={
                "include_system": include_system,
                "page": page,
                "per_page": per_page,
            },
        )
        items = data.get("items", data) if isinstance(data, dict) else data
        return [Pipeline.model_validate(item) for item in items]

    async def get(self, pipeline_id: str) -> Pipeline:
        """Get a pipeline by ID."""
        data = await self._http.get(f"/budpipeline/{pipeline_id}")
        return Pipeline.model_validate(data)

    async def update(
        self,
        pipeline_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        dag: dict[str, Any] | None = None,
        is_active: bool | None = None,
        tags: dict[str, str] | None = None,
    ) -> Pipeline:
        """Update a pipeline."""
        update_data = {}
        if name is not None:
            update_data["name"] = name
        if description is not None:
            update_data["description"] = description
        if dag is not None:
            update_data["dag"] = dag
        if is_active is not None:
            update_data["is_active"] = is_active
        if tags is not None:
            update_data["tags"] = tags

        data = await self._http.patch(f"/budpipeline/{pipeline_id}", json=update_data)
        return Pipeline.model_validate(data)

    async def delete(self, pipeline_id: str) -> None:
        """Delete a pipeline."""
        await self._http.delete(f"/budpipeline/{pipeline_id}")

    async def validate(self, dag: dict[str, Any]) -> ValidationResult:
        """Validate a pipeline DAG."""
        # Convert nodes format to steps format expected by validation API
        api_dag = self._convert_dag_for_validation(dag)
        data = await self._http.post("/budpipeline/validate", json={"dag": api_dag})
        return ValidationResult.model_validate(data)

    def _convert_dag_for_validation(self, dag: dict[str, Any]) -> dict[str, Any]:
        """Convert DAG from DSL format to API validation format."""
        nodes = dag.get("nodes", [])
        metadata = dag.get("metadata", {})

        steps = []
        for node in nodes:
            steps.append({
                "id": node.get("id"),
                "name": node.get("name", node.get("id")),
                "action": node.get("action_id", ""),
                "config": node.get("config", {}),
                "depends_on": node.get("depends_on", []),
            })

        return {
            "name": metadata.get("name", "unnamed-pipeline"),
            "steps": steps,
            "edges": dag.get("edges", []),
        }
