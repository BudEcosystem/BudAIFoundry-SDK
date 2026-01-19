"""Tests for Pipeline DSL."""

from __future__ import annotations

from bud.dsl import Action, Pipeline, parallel, sequence


def test_action_creation() -> None:
    """Test creating an action."""
    action = Action("build", type="docker_build")

    assert action.name == "build"
    assert action.type == "docker_build"


def test_action_after() -> None:
    """Test action dependency with after()."""
    action1 = Action("first")
    action2 = Action("second").after(action1)

    assert action1 in action2._depends_on


def test_action_with_config() -> None:
    """Test action configuration."""
    action = Action("build").with_config(image="python:3.11", tag="latest")

    assert action.config["image"] == "python:3.11"
    assert action.config["tag"] == "latest"


def test_action_with_retry() -> None:
    """Test action retry configuration."""
    action = Action("flaky").with_retry(max_attempts=5, delay=2)

    assert action.retry is not None
    assert action.retry["max_attempts"] == 5
    assert action.retry["delay"] == 2


def test_action_to_node() -> None:
    """Test converting action to DAG node."""
    action = Action("build", type="docker_build")
    action.with_timeout(300)

    node = action.to_node()

    assert node["name"] == "build"
    assert node["action_id"] == "docker_build"
    assert node["timeout"] == 300


def test_pipeline_creation() -> None:
    """Test creating a pipeline."""
    p = Pipeline("deploy")

    assert p.name == "deploy"
    assert len(p._tasks) == 0


def test_pipeline_add_action() -> None:
    """Test adding actions to pipeline."""
    p = Pipeline("test")
    action = Action("step1")
    p.add(action)

    assert len(p._tasks) == 1
    assert p.actions["step1"] == action


def test_pipeline_context_manager() -> None:
    """Test pipeline context manager auto-adds actions."""
    with Pipeline("test") as p:
        build = Action("build")
        test = Action("test").after(build)

    assert len(p._tasks) == 2
    assert "build" in p.actions
    assert "test" in p.actions


def test_pipeline_to_dag() -> None:
    """Test converting pipeline to DAG."""
    with Pipeline("deploy") as p:
        build = Action("build", type="docker_build")
        test = Action("test", type="pytest").after(build)
        deploy = Action("deploy", type="k8s_apply").after(test)

    dag = p.to_dag()

    assert len(dag["nodes"]) == 3
    assert len(dag["edges"]) == 2
    assert dag["metadata"]["name"] == "deploy"


def test_sequence_helper() -> None:
    """Test sequence helper function."""
    t1 = Action("first")
    t2 = Action("second")
    t3 = Action("third")

    last = sequence(t1, t2, t3)

    assert last == t3
    assert t1 in t2._depends_on
    assert t2 in t3._depends_on


def test_parallel_helper() -> None:
    """Test parallel helper function."""
    t1 = Action("a")
    t2 = Action("b")
    t3 = Action("c")

    tasks = parallel(t1, t2, t3)

    assert len(tasks) == 3
    # No dependencies between parallel tasks
    assert len(t1._depends_on) == 0
    assert len(t2._depends_on) == 0
    assert len(t3._depends_on) == 0


def test_sequence_empty_raises_error() -> None:
    """Test that sequence() with no args raises ValueError."""
    import pytest

    with pytest.raises(ValueError, match="requires at least one action"):
        sequence()


def test_sequence_single_action() -> None:
    """Test sequence with a single action returns that action."""
    t1 = Action("only")
    result = sequence(t1)

    assert result == t1
    assert len(t1._depends_on) == 0
