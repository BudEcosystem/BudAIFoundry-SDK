# Task Management

Retrieve, list, cancel, and subscribe to A2A tasks.

> **Examples**: See [a2a_example.py](../../examples/a2a_example.py) for working code examples.

## Task Lifecycle

Tasks progress through defined states. Terminal states cannot be restarted.

```
SUBMITTED → WORKING → COMPLETED (terminal)
                    → FAILED (terminal)
                    → CANCELED (terminal)
                    → REJECTED (terminal)
                    → INPUT_REQUIRED → (follow-up message) → WORKING
                    → AUTH_REQUIRED → (resolve auth) → WORKING
```

| State | Terminal | Description |
|-------|----------|-------------|
| `SUBMITTED` | No | Task acknowledged, not yet processing |
| `WORKING` | No | Actively being processed |
| `INPUT_REQUIRED` | No | Agent needs more input from client |
| `AUTH_REQUIRED` | No | Authentication required to proceed |
| `COMPLETED` | Yes | Finished successfully |
| `FAILED` | Yes | Finished with an error |
| `CANCELED` | Yes | Canceled before completion |
| `REJECTED` | Yes | Agent decided not to perform the task |

## get_task()

Retrieve the current state of an existing task by ID.

### Function Signature

```python
client.a2a.get_task(
    agent_name: str,
    *,
    task_id: str,
    version: int | None = None,
    history_length: int | None = None,
    tenant: str | None = None,
) -> Task
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `agent_name` | `str` | required | Name of the agent |
| `task_id` | `str` | required | Task identifier |
| `version` | `int \| None` | `None` | Agent deployment version |
| `history_length` | `int \| None` | `None` | Max history messages to include |
| `tenant` | `str \| None` | `None` | Tenant identifier (v1.0 only) |

### Example

```python
# Send a message to create a task
result = client.a2a.send_message("my-agent", message="Hello!")
task_id = result.task.id

# Retrieve the task later
task = client.a2a.get_task("my-agent", task_id=task_id)
print(f"Status: {task.status.state}")
print(f"Context: {task.context_id}")

if task.artifacts:
    for artifact in task.artifacts:
        for part in artifact.parts:
            if part.text:
                print(f"Output: {part.text}")

if task.history:
    print(f"Messages: {len(task.history)}")
```

## list_tasks()

List tasks with pagination and filters. **Available in A2A v1.0 only.**

### Function Signature

```python
client.a2a.list_tasks(
    agent_name: str,
    *,
    version: int | None = None,
    tenant: str | None = None,
    context_id: str | None = None,
    status: TaskState | str | None = None,
    page_size: int | None = None,
    page_token: str | None = None,
    history_length: int | None = None,
    status_timestamp_after: str | None = None,
    include_artifacts: bool | None = None,
) -> ListTasksResponse
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `agent_name` | `str` | required | Name of the agent |
| `version` | `int \| None` | `None` | Agent deployment version |
| `tenant` | `str \| None` | `None` | Tenant identifier |
| `context_id` | `str \| None` | `None` | Filter by conversation context |
| `status` | `TaskState \| str \| None` | `None` | Filter by task state |
| `page_size` | `int \| None` | `None` | Results per page (1-100, default 50) |
| `page_token` | `str \| None` | `None` | Cursor from previous response |
| `history_length` | `int \| None` | `None` | Max history messages per task |
| `status_timestamp_after` | `str \| None` | `None` | ISO 8601 timestamp filter |
| `include_artifacts` | `bool \| None` | `None` | Include artifacts (default false) |

### Response: ListTasksResponse

| Field | Type | Description |
|-------|------|-------------|
| `tasks` | `list[Task]` | Matching tasks |
| `next_page_token` | `str` | Cursor for next page (empty = no more) |
| `page_size` | `int` | Page size used |
| `total_size` | `int` | Total tasks available |

### Example

```python
from bud.models.a2a import TaskState

# Requires v1.0
client = BudClient(api_key="your-key", a2a_version="1.0")

# List recent tasks
result = client.a2a.list_tasks("my-agent", page_size=10)
print(f"Total: {result.total_size}")
for task in result.tasks:
    print(f"  {task.id}: {task.status.state}")

# Filter by status
working = client.a2a.list_tasks("my-agent", status=TaskState.WORKING)

# Filter by context
ctx_tasks = client.a2a.list_tasks("my-agent", context_id="ctx-123")
```

### Pagination

```python
# First page
page1 = client.a2a.list_tasks("my-agent", page_size=10)

# Next page (if available)
if page1.next_page_token:
    page2 = client.a2a.list_tasks("my-agent", page_size=10, page_token=page1.next_page_token)
```

### v0.3 Note

`list_tasks()` raises `A2AError` when called with v0.3. The ListTasks method only exists in A2A v1.0.

```python
from bud.exceptions import A2AError

client = BudClient(api_key="key")  # default v0.3
try:
    client.a2a.list_tasks("agent")
except A2AError as e:
    print(e)  # "ListTasks is only available in A2A v1.0."
```

## cancel_task()

Cancel a running task. Fails if the task is already in a terminal state.

### Function Signature

```python
client.a2a.cancel_task(
    agent_name: str,
    *,
    task_id: str,
    version: int | None = None,
    tenant: str | None = None,
) -> Task
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `agent_name` | `str` | required | Name of the agent |
| `task_id` | `str` | required | Task identifier |
| `version` | `int \| None` | `None` | Agent deployment version |
| `tenant` | `str \| None` | `None` | Tenant identifier (v1.0 only) |

### Example

```python
from bud.exceptions import A2AError

try:
    task = client.a2a.cancel_task("my-agent", task_id="task-123")
    print(f"Cancelled: {task.status.state}")
except A2AError as e:
    print(f"Cancel failed: {e}")
    if e.code == -32002:
        print("Task already completed — cannot cancel")
```

## subscribe_to_task()

Subscribe to real-time updates for an existing task via SSE stream. The first event is always the current task state.

### Function Signature

```python
client.a2a.subscribe_to_task(
    agent_name: str,
    *,
    task_id: str,
    version: int | None = None,
    tenant: str | None = None,
) -> A2AStream
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `agent_name` | `str` | required | Name of the agent |
| `task_id` | `str` | required | Task ID to subscribe to |
| `version` | `int \| None` | `None` | Agent deployment version |
| `tenant` | `str \| None` | `None` | Tenant identifier (v1.0 only) |

### Stream Events

The stream yields the same event types as streaming `send_message`:

| Event Type | Description |
|------------|-------------|
| `Task` | Current task state (always first event) |
| `TaskStatusUpdateEvent` | State transition |
| `TaskArtifactUpdateEvent` | Output chunk |
| `Message` | Direct message from agent |

### Difference from send_message(stream=True)

| | `send_message(stream=True)` | `subscribe_to_task()` |
|-|-------|---------|
| **Purpose** | Send a new message | Monitor an existing task |
| **Input** | `message` parameter | `task_id` parameter |
| **Creates work** | Yes | No |
| **When to use** | Starting or continuing a task | Reconnecting or monitoring |

### Example

```python
from bud.models.a2a import Task, TaskStatusUpdateEvent, TaskArtifactUpdateEvent

# Subscribe to a task created earlier
stream = client.a2a.subscribe_to_task("my-agent", task_id="task-123")

for event in stream:
    if isinstance(event, Task):
        print(f"Current state: {event.status.state}")
    elif isinstance(event, TaskStatusUpdateEvent):
        print(f"Status changed: {event.status.state}")
    elif isinstance(event, TaskArtifactUpdateEvent):
        for part in event.artifact.parts:
            if part.text:
                print(part.text, end="")

print(f"\nFinal: {stream.final_task.status.state}")
```

## Best Practices

- Use `get_task()` for polling task status when streaming isn't available
- Use `subscribe_to_task()` instead of polling when the agent supports streaming
- Always handle `A2AError` on `cancel_task()` — the task may already be complete
- Use `list_tasks()` with `context_id` to find all tasks in a conversation
- Set `include_artifacts=True` on `list_tasks()` only when you need artifact content — it increases response size
- For pagination, iterate until `next_page_token` is empty
