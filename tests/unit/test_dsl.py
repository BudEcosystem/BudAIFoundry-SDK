"""Tests for Pipeline DSL."""

from __future__ import annotations

import pytest

from bud.dsl import Pipeline, Task, parallel, sequence


def test_task_creation() -> None:
    """Test creating a task."""
    task = Task("build", action="bud.docker.build")

    assert task.name == "build"
    assert task.action == "bud.docker.build"


def test_task_after() -> None:
    """Test task dependency with after()."""
    task1 = Task("first")
    task2 = Task("second").after(task1)

    assert task1 in task2._depends_on


def test_task_with_config() -> None:
    """Test task configuration."""
    task = Task("build").with_config(image="python:3.11", tag="latest")

    assert task.config["image"] == "python:3.11"
    assert task.config["tag"] == "latest"


def test_task_with_retry() -> None:
    """Test task retry configuration."""
    task = Task("flaky").with_retry(max_attempts=5, delay=2)

    assert task.retry["max_attempts"] == 5
    assert task.retry["delay"] == 2


def test_task_to_node() -> None:
    """Test converting task to DAG node."""
    task = Task("build", action="bud.docker.build")
    task.with_timeout(300)

    node = task.to_node()

    assert node["name"] == "build"
    assert node["action_id"] == "bud.docker.build"
    assert node["timeout"] == 300


def test_pipeline_creation() -> None:
    """Test creating a pipeline."""
    p = Pipeline("deploy")

    assert p.name == "deploy"
    assert len(p._tasks) == 0


def test_pipeline_add_task() -> None:
    """Test adding tasks to pipeline."""
    p = Pipeline("test")
    task = Task("step1")
    p.add(task)

    assert len(p._tasks) == 1
    assert p.tasks["step1"] == task


def test_pipeline_context_manager() -> None:
    """Test pipeline context manager auto-adds tasks."""
    with Pipeline("test") as p:
        build = Task("build")
        test = Task("test").after(build)

    assert len(p._tasks) == 2
    assert "build" in p.tasks
    assert "test" in p.tasks


def test_pipeline_to_dag() -> None:
    """Test converting pipeline to DAG."""
    with Pipeline("deploy") as p:
        build = Task("build", action="bud.docker.build")
        test = Task("test", action="bud.test.pytest").after(build)
        deploy = Task("deploy", action="bud.k8s.apply").after(test)

    dag = p.to_dag()

    assert len(dag["nodes"]) == 3
    assert len(dag["edges"]) == 2
    assert dag["metadata"]["name"] == "deploy"


def test_sequence_helper() -> None:
    """Test sequence helper function."""
    t1 = Task("first")
    t2 = Task("second")
    t3 = Task("third")

    last = sequence(t1, t2, t3)

    assert last == t3
    assert t1 in t2._depends_on
    assert t2 in t3._depends_on


def test_parallel_helper() -> None:
    """Test parallel helper function."""
    t1 = Task("a")
    t2 = Task("b")
    t3 = Task("c")

    tasks = parallel(t1, t2, t3)

    assert len(tasks) == 3
    # No dependencies between parallel tasks
    assert len(t1._depends_on) == 0
    assert len(t2._depends_on) == 0
    assert len(t3._depends_on) == 0
