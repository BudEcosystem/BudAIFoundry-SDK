# Sending Messages

Send messages to A2A agents with blocking or streaming responses, and continue conversations with multi-turn support.

> **Examples**: See [a2a_example.py](../../examples/a2a_example.py) for working code examples.

## Basic Usage

```python
from bud import BudClient

client = BudClient(api_key="your-key")

result = client.a2a.send_message("my-agent", message="What is 2 + 2?")
if result.task:
    print(result.task.status.state)
    for artifact in result.task.artifacts or []:
        for part in artifact.parts:
            if part.text:
                print(part.text)
```

## Function Signature

```python
client.a2a.send_message(
    agent_name: str,
    *,
    message: str | Message | dict[str, Any],
    stream: bool = False,
    version: int | None = None,
    context_id: str | None = None,
    task_id: str | None = None,
    configuration: SendMessageConfiguration | dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> SendMessageResponse  # stream=False
   | A2AStream             # stream=True
```

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `agent_name` | `str` | required | Name of the A2A agent |
| `message` | `str \| Message \| dict` | required | Text string, Message object, or raw dict |
| `stream` | `bool` | `False` | If `True`, returns an `A2AStream` for SSE events |
| `version` | `int \| None` | `None` | Agent deployment version (`None` = v0/latest) |
| `context_id` | `str \| None` | `None` | Conversation context ID for multi-turn |
| `task_id` | `str \| None` | `None` | Existing task ID (for input-required follow-ups) |
| `configuration` | `SendMessageConfiguration \| dict \| None` | `None` | Request configuration |
| `metadata` | `dict \| None` | `None` | Optional key-value metadata |

### Message Input

The `message` parameter accepts three formats:

```python
# 1. Simple string (most common)
result = client.a2a.send_message("agent", message="Hello!")

# 2. Message object (full control)
from bud.models.a2a import Message, Part, Role
msg = Message(role=Role.USER, parts=[Part(text="Hello!")])
result = client.a2a.send_message("agent", message=msg)

# 3. Dict (raw format)
result = client.a2a.send_message("agent", message={
    "role": "user",
    "parts": [{"text": "Hello!"}]
})
```

### Configuration

```python
from bud.models.a2a import SendMessageConfiguration

config = SendMessageConfiguration(
    accepted_output_modes=["text/plain", "application/json"],
    history_length=10,
)
result = client.a2a.send_message("agent", message="Hello!", configuration=config)
```

| Field | Type | Description |
|-------|------|-------------|
| `accepted_output_modes` | `list[str]` | Media types the client accepts |
| `history_length` | `int` | Max recent messages to return |
| `blocking` | `bool` | Block until completion (v0.3) |
| `return_immediately` | `bool` | Return immediately (v1.0) |

## Response: SendMessageResponse

The response contains either a `task` or a `message` (one is always `None`):

```python
result = client.a2a.send_message("agent", message="Hello!")

if result.task:
    # Agent created a tracked task
    print(result.task.id)
    print(result.task.status.state)
    print(result.task.context_id)
    for artifact in result.task.artifacts or []:
        for part in artifact.parts:
            print(part.text)

elif result.message:
    # Agent responded directly (no task tracking)
    for part in result.message.parts:
        print(part.text)
```

## Streaming

Pass `stream=True` to receive Server-Sent Events in real-time:

```python
from bud.models.a2a import TaskArtifactUpdateEvent, TaskStatusUpdateEvent, Task

stream = client.a2a.send_message("my-agent", message="Tell me a story", stream=True)

for event in stream:
    if isinstance(event, TaskArtifactUpdateEvent):
        for part in event.artifact.parts:
            if part.text:
                print(part.text, end="", flush=True)
    elif isinstance(event, TaskStatusUpdateEvent):
        print(f"\nStatus: {event.status.state}")
    elif isinstance(event, Task):
        print(f"Task: {event.id}")

print()
```

### Stream Event Types

| Event Type | Description |
|------------|-------------|
| `Task` | Initial task snapshot or final state |
| `TaskStatusUpdateEvent` | Task state transition (working, completed, etc.) |
| `TaskArtifactUpdateEvent` | Output chunk (text, data, file) |
| `Message` | Direct message from agent |

### final_task Property

After consuming the stream, access the last `Task` object:

```python
stream = client.a2a.send_message("agent", message="Hello", stream=True)
for event in stream:
    pass  # process events

if stream.final_task:
    print(f"Final status: {stream.final_task.status.state}")
```

### Context Manager

```python
with client.a2a.send_message("agent", message="Hello", stream=True) as stream:
    for event in stream:
        pass  # process events
```

## Multi-Turn Conversations

Use `context_id` to maintain conversation state across messages.

### Basic Multi-Turn

```python
# First message
r1 = client.a2a.send_message("agent", message="Convert 100 USD")

if r1.task:
    # Second message — same conversation
    r2 = client.a2a.send_message(
        "agent",
        message="to EUR",
        context_id=r1.task.context_id,
    )
```

### Input-Required Flow

When an agent needs clarification, it returns `INPUT_REQUIRED` status:

```python
from bud.models.a2a import TaskState

r1 = client.a2a.send_message("agent", message="Book a flight")

if r1.task and r1.task.status.state == TaskState.INPUT_REQUIRED:
    # Agent asked a question — check status message
    if r1.task.status.message:
        for part in r1.task.status.message.parts:
            print(f"Agent asks: {part.text}")

    # Respond with the answer
    r2 = client.a2a.send_message(
        "agent",
        message="New York to London, next Monday",
        context_id=r1.task.context_id,
        task_id=r1.task.id,
    )
```

## Examples

### 1. Simple Text Message

```python
result = client.a2a.send_message("my-agent", message="What is Python?")
if result.task and result.task.artifacts:
    print(result.task.artifacts[0].parts[0].text)
```

### 2. Streaming with Progress

```python
stream = client.a2a.send_message("my-agent", message="Write a haiku", stream=True)
for event in stream:
    if isinstance(event, TaskArtifactUpdateEvent):
        for part in event.artifact.parts:
            if part.text:
                print(part.text, end="")
print()
```

### 3. Specific Agent Version

```python
# Use agent deployment version 2
result = client.a2a.send_message("my-agent", message="Hello", version=2)
```

### 4. With Metadata

```python
result = client.a2a.send_message(
    "my-agent",
    message="Analyze this",
    metadata={"source": "dashboard", "user_id": "u123"},
)
```

## Best Practices

- Use `stream=True` for long-running tasks to get real-time progress
- Always check `result.task` vs `result.message` — agents can return either
- Store `context_id` from the first response for multi-turn conversations
- Use `task_id` only when responding to `INPUT_REQUIRED` status
- Close the client when done: `client.close()` or use as context manager
