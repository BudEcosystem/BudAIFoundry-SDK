"""Pipeline DSL for defining pipelines in Python.

This module provides a fluent interface for building pipeline DAGs.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Action:
    """An action in a pipeline DAG.

    Example:
        ```python
        from bud import Action

        start = Action("start", type="log")
        transform = Action("transform", type="transform").after(start)
        notify = Action("notify", type="notification").after(transform)
        ```
    """

    name: str
    type: str | None = None
    config: dict[str, Any] = field(default_factory=dict)
    timeout: int | None = None
    retry: dict[str, Any] | None = None
    condition: str | None = None

    # Internal state
    _id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    _depends_on: list[Action] = field(default_factory=list)
    _pipeline: Pipeline | None = field(default=None, repr=False)

    def after(self, *tasks: Action) -> Action:
        """Set this task to run after the given tasks.

        Args:
            *tasks: Actions that must complete before this one

        Returns:
            Self for chaining
        """
        self._depends_on.extend(tasks)
        return self

    def with_config(self, **config: Any) -> Action:
        """Set task configuration.

        Args:
            **config: Configuration key-value pairs

        Returns:
            Self for chaining
        """
        self.config.update(config)
        return self

    def with_timeout(self, seconds: int) -> Action:
        """Set task timeout.

        Args:
            seconds: Timeout in seconds

        Returns:
            Self for chaining
        """
        self.timeout = seconds
        return self

    def with_retry(
        self,
        max_attempts: int = 3,
        delay: int = 1,
        backoff: float = 2.0,
    ) -> Action:
        """Configure retry behavior.

        Args:
            max_attempts: Maximum retry attempts
            delay: Initial delay between retries in seconds
            backoff: Backoff multiplier

        Returns:
            Self for chaining
        """
        self.retry = {
            "max_attempts": max_attempts,
            "delay": delay,
            "backoff": backoff,
        }
        return self

    def when(self, condition: str) -> Action:
        """Set a condition for this task.

        Args:
            condition: Condition expression

        Returns:
            Self for chaining
        """
        self.condition = condition
        return self

    def to_node(self) -> dict[str, Any]:
        """Convert to DAG node representation."""
        node: dict[str, Any] = {
            "id": self._id,
            "type": "action",
            "name": self.name,
            "depends_on": [t._id for t in self._depends_on],
        }

        if self.type:
            node["action_id"] = self.type
        if self.config:
            node["config"] = self.config
        if self.timeout:
            node["timeout"] = self.timeout
        if self.retry:
            node["retry"] = self.retry
        if self.condition:
            node["condition"] = self.condition

        return node


@dataclass
class Pipeline:
    """A pipeline definition using Python DSL.

    Example:
        ```python
        from bud import Pipeline, Action

        with Pipeline("my-pipeline") as p:
            start = Action("start", type="log")
            transform = Action("transform", type="transform").after(start)
            notify = Action("notify", type="notification").after(transform)

        # Register with API
        client.pipelines.create(p.to_dag(), name=p.name)
        ```

    Or without context manager:
        ```python
        p = Pipeline("my-pipeline")
        p.add(Action("step1", type="http_request"))
        p.add(Action("step2", type="notification").after(p.actions["step1"]))
        ```
    """

    name: str
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    # Internal state
    _tasks: list[Action] = field(default_factory=list)
    _active: bool = field(default=False, repr=False)

    @property
    def actions(self) -> dict[str, Action]:
        """Get actions by name."""
        return {t.name: t for t in self._tasks}

    def add(self, task: Action) -> Action:
        """Add a task to the pipeline.

        Args:
            task: Action to add

        Returns:
            The added task
        """
        task._pipeline = self
        self._tasks.append(task)
        return task

    def action(
        self,
        name: str,
        type: str | None = None,
        **config: Any,
    ) -> Action:
        """Create and add an action.

        Args:
            name: Action name
            type: Action type (e.g., "log", "transform")
            **config: Action configuration

        Returns:
            Created action
        """
        a = Action(name=name, type=type, config=config)
        return self.add(a)

    def to_dag(self) -> dict[str, Any]:
        """Convert to DAG representation for API.

        Returns:
            DAG dictionary
        """
        nodes = [t.to_node() for t in self._tasks]

        # Build edges from dependencies
        edges = []
        for task in self._tasks:
            for dep in task._depends_on:
                edges.append({"from": dep._id, "to": task._id})

        return {
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "name": self.name,
                "description": self.description,
                **self.metadata,
            },
        }

    def __enter__(self) -> Pipeline:
        """Enter pipeline context."""
        self._active = True
        _pipeline_context.set(self)
        return self

    def __exit__(self, *args: Any) -> None:
        """Exit pipeline context."""
        self._active = False
        _pipeline_context.clear()


class _PipelineContext:
    """Thread-local pipeline context."""

    def __init__(self) -> None:
        self._pipeline: Pipeline | None = None

    def set(self, pipeline: Pipeline) -> None:
        self._pipeline = pipeline

    def clear(self) -> None:
        self._pipeline = None

    def get(self) -> Pipeline | None:
        return self._pipeline


_pipeline_context = _PipelineContext()


# Auto-register tasks when created inside a Pipeline context
_original_task_init = Action.__init__


def _task_init_with_context(self: Action, *args: Any, **kwargs: Any) -> None:
    _original_task_init(self, *args, **kwargs)
    pipeline = _pipeline_context.get()
    if pipeline is not None:
        pipeline.add(self)


Action.__init__ = _task_init_with_context  # type: ignore


# Convenience functions for building pipelines
def parallel(*tasks: Action) -> list[Action]:
    """Mark tasks to run in parallel (no dependencies between them).

    Args:
        *tasks: Actions to run in parallel

    Returns:
        List of tasks
    """
    return list(tasks)


def sequence(*tasks: Action) -> Action:
    """Chain tasks in sequence.

    Args:
        *tasks: Actions to chain (must have at least one)

    Returns:
        Last task in the sequence

    Raises:
        ValueError: If no tasks provided
    """
    if not tasks:
        raise ValueError("sequence() requires at least one action")
    for i in range(1, len(tasks)):
        tasks[i].after(tasks[i - 1])
    return tasks[-1]


def load_pipeline_file(path: str) -> Pipeline:
    """Load a pipeline from a Python file.

    The file should define a pipeline using the DSL.
    The pipeline is expected to be named 'pipeline' or 'p'.

    Args:
        path: Path to Python file

    Returns:
        Loaded pipeline
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("pipeline_module", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Could not load pipeline from {path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Look for pipeline in module
    pipeline = getattr(module, "pipeline", None) or getattr(module, "p", None)

    if pipeline is None:
        raise ValueError(
            f"No pipeline found in {path}. " "Define a variable named 'pipeline' or 'p'."
        )

    if not isinstance(pipeline, Pipeline):
        raise ValueError(
            f"Expected Pipeline, got {type(pipeline).__name__}. "
            "Use 'with Pipeline(...) as pipeline:' to define your pipeline."
        )

    return pipeline
