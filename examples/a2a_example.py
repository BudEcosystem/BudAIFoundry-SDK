#!/usr/bin/env python3
"""A2A (Agent-to-Agent) protocol examples using the BudAI SDK.

Demonstrates how to interact with A2A agents deployed via the BudAI gateway.
The A2A protocol uses JSON-RPC 2.0 over HTTP with SSE streaming support.

Examples covered:

* **Agent Card Discovery** — fetch agent metadata (name, capabilities, skills)
  via ``client.a2a.get_agent_card()``.
* **Send Message (Blocking)** — send a text message and receive a Task with
  artifacts via ``client.a2a.send_message()``.
* **Streaming** — stream responses in real-time via SSE using
  ``client.a2a.send_message(stream=True)``.
* **Multi-Turn Conversation** — continue a conversation using ``context_id``
  to maintain state across multiple messages.
* **Task Management** — retrieve task status with ``client.a2a.get_task()``
  and attempt cancellation with ``client.a2a.cancel_task()``.
* **Version Switching** — switch between A2A protocol v0.3 and v1.0 at
  runtime via ``client.a2a.a2a_version``.
* **List Tasks** — paginated task listing with filters via
  ``client.a2a.list_tasks()`` (v1.0 only).
* **Subscribe to Task** — monitor task updates via SSE stream using
  ``client.a2a.subscribe_to_task()``.
* **Extended Agent Card** — fetch authenticated extended card via
  ``client.a2a.get_extended_agent_card()`` (JSON-RPC POST, not GET).

SDK methods used::

    client.a2a.get_agent_card(agent_name, version=...)
    client.a2a.send_message(agent_name, message=..., stream=..., version=...,
                            context_id=..., task_id=...)
    client.a2a.get_task(agent_name, task_id=..., version=..., tenant=...)
    client.a2a.cancel_task(agent_name, task_id=..., version=..., tenant=...)
    client.a2a.list_tasks(agent_name, version=..., page_size=..., context_id=...)
    client.a2a.subscribe_to_task(agent_name, task_id=..., version=...)
    client.a2a.get_extended_agent_card(agent_name, version=..., tenant=...)

Usage:
    python examples/a2a_example.py
"""

from __future__ import annotations

from bud import BudClient
from bud.exceptions import A2AError
from bud.models.a2a import TaskArtifactUpdateEvent, TaskState, TaskStatusUpdateEvent

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "https://gateway.dev.bud.studio"
API_KEY = "bud_admin_1kyBHfsH66wrU5UM2uuwlUwAudHkaM5V3_q4JtoJI3w"
AGENT_NAME = "test-backend-kimi"
AGENT_VERSION = 1  # Agent deployment version (v1)


# ---------------------------------------------------------------------------
# Example 1: Agent Card Discovery
# ---------------------------------------------------------------------------


def example_get_agent_card():
    """Example 1: Discover agent capabilities."""
    print("=" * 60)
    print("Example 1: Get Agent Card")
    print("=" * 60)

    client = BudClient(api_key=API_KEY, base_url=BASE_URL, a2a_version="1.0")

    card = client.a2a.get_agent_card(AGENT_NAME, version=AGENT_VERSION)

    print(f"Agent: {card.name}")
    print(f"Description: {card.description}")
    if card.capabilities:
        print(f"Streaming: {card.capabilities.streaming}")
    if card.skills:
        for skill in card.skills:
            print(f"  Skill: {skill.name} - {skill.description}")
    print()

    client.close()


# ---------------------------------------------------------------------------
# Example 2: Send Message (Blocking)
# ---------------------------------------------------------------------------


def example_send_message():
    """Example 2: Send a simple text message (blocking)."""
    print("=" * 60)
    print("Example 2: Send Message (Blocking)")
    print("=" * 60)

    client = BudClient(api_key=API_KEY, base_url=BASE_URL, a2a_version="1.0")

    result = client.a2a.send_message(AGENT_NAME, message="What is 2 + 2?", version=AGENT_VERSION)

    if result.task:
        print(f"Task ID: {result.task.id}")
        print(f"Status: {result.task.status.state}")
        if result.task.artifacts:
            for artifact in result.task.artifacts:
                for part in artifact.parts:
                    if part.text:
                        print(f"Response: {part.text}")
    elif result.message:
        for part in result.message.parts:
            if part.text:
                print(f"Response: {part.text}")
    print()

    client.close()


# ---------------------------------------------------------------------------
# Example 3: Streaming
# ---------------------------------------------------------------------------


def example_streaming():
    """Example 3: Send a streaming message."""
    print("=" * 60)
    print("Example 3: Streaming Message")
    print("=" * 60)

    client = BudClient(api_key=API_KEY, base_url=BASE_URL, a2a_version="0.3")

    print("Streaming response: ", end="", flush=True)
    stream = client.a2a.send_message(
        AGENT_NAME, message="Tell me a short story of 2 sentences", stream=True, version=AGENT_VERSION
    )
    for event in stream:
        if isinstance(event, TaskArtifactUpdateEvent):
            for part in event.artifact.parts:
                if part.text:
                    print(part.text, end="", flush=True)
    print("\n")

    if stream.final_task:
        print(f"Final status: {stream.final_task.status.state}")
    print()

    client.close()


# ---------------------------------------------------------------------------
# Example 4: Multi-Turn Conversation
# ---------------------------------------------------------------------------


def example_multi_turn():
    """Example 4: Multi-turn conversation using context_id."""
    print("=" * 60)
    print("Example 4: Multi-Turn Conversation")
    print("=" * 60)

    client = BudClient(api_key=API_KEY, base_url=BASE_URL, a2a_version="1.0")

    # First message
    r1 = client.a2a.send_message(AGENT_NAME, message="Convert 100 USD in INR", version=AGENT_VERSION)
    if r1.task:
        print(f"First Response: {r1.task.status.state}")
        if r1.task.artifacts:
            for part in r1.task.artifacts[0].parts:
                if part.text:
                    print(f"Result: {part.text}")

        # Follow-up with context_id to maintain conversation state
        r2 = client.a2a.send_message(
            AGENT_NAME,
            message="EUR",
            context_id=r1.task.context_id,
            version=AGENT_VERSION,
        )
        if r2.task:
            print(f"Follow-up status: {r2.task.status.state}")
            if r2.task.artifacts:
                for part in r2.task.artifacts[0].parts:
                    if part.text:
                        print(f"Result: {part.text}")

    client.close()


# ---------------------------------------------------------------------------
# Example 5: Task Management (Get + Cancel)
# ---------------------------------------------------------------------------


def example_cancel_task():
    """Example 5: Get and cancel tasks."""
    print("=" * 60)
    print("Example 5: Task Management")
    print("=" * 60)

    client = BudClient(api_key=API_KEY, base_url=BASE_URL, a2a_version="1.0")

    # Send a message first
    result = client.a2a.send_message(AGENT_NAME, message="Hello!", version=AGENT_VERSION)
    if result.task:
        task_id = result.task.id
        print(f"Created task: {task_id}")

        # Get task status
        task = client.a2a.get_task(AGENT_NAME, task_id=task_id, version=AGENT_VERSION)
        print(f"Task status: {task.status.state}")

        # Cancel task — may fail if task already completed
        try:
            cancelled = client.a2a.cancel_task(AGENT_NAME, task_id=task_id, version=AGENT_VERSION)
            print(f"Cancelled: {cancelled.status.state}")
        except A2AError as e:
            print(f"Cancel failed: {e}")
            if e.code:
                print(f"  Error code: {e.code}")
            if e.data:
                print(f"  Error data: {e.data}")
        except Exception as e:
            print(f"Cancel failed: {type(e).__name__}: {e}")

    client.close()


# ---------------------------------------------------------------------------
# Example 6: Version Switching
# ---------------------------------------------------------------------------


def example_version_switch():
    """Example 6: Switch between v0.3 and v1.0."""
    print("=" * 60)
    print("Example 6: Version Switching")
    print("=" * 60)

    # Default: v0.3
    client = BudClient(api_key=API_KEY, base_url=BASE_URL)
    print(f"Default version: {client.a2a.a2a_version}")

    # Switch to v1.0 at runtime
    client.a2a.a2a_version = "1.0"
    print(f"Switched to: {client.a2a.a2a_version}")

    client.close()


# ---------------------------------------------------------------------------
# Example 7: List Tasks (v1.0 only)
# ---------------------------------------------------------------------------


def example_list_tasks():
    """Example 7: List tasks with pagination."""
    print("=" * 60)
    print("Example 7: List Tasks (v1.0 only)")
    print("=" * 60)

    client = BudClient(api_key=API_KEY, base_url=BASE_URL, a2a_version="1.0")

    result = client.a2a.list_tasks(AGENT_NAME, version=AGENT_VERSION, page_size=5)

    print(f"Total tasks: {result.total_size}")
    print(f"Page size: {result.page_size}")
    print(f"Next page token: {result.next_page_token or '(none)'}")
    for task in result.tasks:
        print(f"  Task {task.id}: {task.status.state}")
    print()

    client.close()


# ---------------------------------------------------------------------------
# Example 8: Subscribe to Task
# ---------------------------------------------------------------------------


def example_subscribe_to_task():
    """Example 8: Subscribe to task updates via SSE."""
    print("=" * 60)
    print("Example 8: Subscribe to Task")
    print("=" * 60)

    client = BudClient(api_key=API_KEY, base_url=BASE_URL, a2a_version="1.0")

    # Send a message first to get a task
    result = client.a2a.send_message(AGENT_NAME, message="Hello!", version=AGENT_VERSION)
    if result.task:
        task_id = result.task.id
        print(f"Created task: {task_id}")

        # Subscribe to task updates
        try:
            stream = client.a2a.subscribe_to_task(AGENT_NAME, task_id=task_id, version=AGENT_VERSION)
            for event in stream:
                if isinstance(event, TaskStatusUpdateEvent):
                    print(f"  Status update: {event.status.state}")
                elif isinstance(event, TaskArtifactUpdateEvent):
                    for part in event.artifact.parts:
                        if part.text:
                            print(f"  Artifact: {part.text[:100]}")
                else:
                    print(f"  Event: {type(event).__name__}")
        except A2AError as e:
            print(f"Subscribe failed: {e}")
    print()

    client.close()


# ---------------------------------------------------------------------------
# Example 9: Get Extended Agent Card
# ---------------------------------------------------------------------------


def example_get_extended_agent_card():
    """Example 9: Get authenticated extended agent card."""
    print("=" * 60)
    print("Example 9: Get Extended Agent Card")
    print("=" * 60)

    client = BudClient(api_key=API_KEY, base_url=BASE_URL, a2a_version="1.0")

    try:
        card = client.a2a.get_extended_agent_card(AGENT_NAME, version=AGENT_VERSION)
        print(f"Agent: {card.name}")
        print(f"Description: {card.description}")
        if card.capabilities:
            print(f"Streaming: {card.capabilities.streaming}")
        if card.skills:
            print(f"Skills: {len(card.skills)}")
            for skill in card.skills:
                print(f"  - {skill.name}")
    except A2AError as e:
        print(f"Extended card failed: {e}")
        if e.code:
            print(f"  Error code: {e.code}")
    print()

    client.close()


# ---------------------------------------------------------------------------
# Example 10: Get Task
# ---------------------------------------------------------------------------


def example_get_task():
    """Example 10: Retrieve a task by ID."""
    print("=" * 60)
    print("Example 10: Get Task")
    print("=" * 60)

    client = BudClient(api_key=API_KEY, base_url=BASE_URL, a2a_version="1.0")

    # Send a message first to create a task
    result = client.a2a.send_message(AGENT_NAME, message="What is Python?", version=AGENT_VERSION)
    if result.task:
        task_id = result.task.id
        print(f"Created task: {task_id}")

        # Retrieve the task by ID
        task = client.a2a.get_task(AGENT_NAME, task_id=task_id, version=AGENT_VERSION)
        print(f"Task ID: {task.id}")
        print(f"Context ID: {task.context_id}")
        print(f"Status: {task.status.state}")
        if task.status.timestamp:
            print(f"Timestamp: {task.status.timestamp}")
        if task.artifacts:
            print(f"Artifacts: {len(task.artifacts)}")
            for artifact in task.artifacts:
                for part in artifact.parts:
                    if part.text:
                        print(f"  Response: {part.text[:200]}")
        if task.history:
            print(f"History: {len(task.history)} messages")
    print()

    client.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    print("\n Bud SDK A2A Protocol Examples\n")

    if not API_KEY:
        print("Error: API_KEY is not set.")
        print("Update the API_KEY constant at the top of this file.")
        exit(1)

    # Run examples
    try:
        example_get_agent_card()
    except Exception as e:
        print(f"Example 1 failed: {e}\n")

    try:
        example_send_message()
    except Exception as e:
        print(f"Example 2 failed: {e}\n")

    try:
        example_streaming()
    except Exception as e:
        print(f"Example 3 failed: {e}\n")

    try:
        example_multi_turn()
    except Exception as e:
        print(f"Example 4 failed: {e}\n")

    try:
        example_cancel_task()
    except Exception as e:
        print(f"Example 5 failed: {e}\n")

    try:
        example_version_switch()
    except Exception as e:
        print(f"Example 6 failed: {e}\n")

    try:
        example_list_tasks()
    except Exception as e:
        print(f"Example 7 failed: {e}\n")

    try:
        example_subscribe_to_task()
    except Exception as e:
        print(f"Example 8 failed: {e}\n")

    try:
        example_get_extended_agent_card()
    except Exception as e:
        print(f"Example 9 failed: {e}\n")

    try:
        example_get_task()
    except Exception as e:
        print(f"Example 10 failed: {e}\n")

    print("Examples complete!")


if __name__ == "__main__":
    main()
