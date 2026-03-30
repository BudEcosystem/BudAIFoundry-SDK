# A2A (Agent-to-Agent) Protocol

Interact with A2A agents using the BudAI SDK. The A2A protocol enables agent-to-agent communication over JSON-RPC 2.0 with SSE streaming support.

> **Examples**: See [a2a_example.py](../../examples/a2a_example.py) for working code examples.

| Method | Description |
|--------|-------------|
| `send_message()` | Send a message to an agent (blocking or streaming) |
| `get_task()` | Retrieve the state of an existing task |
| `list_tasks()` | List tasks with pagination and filters (v1.0 only) |
| `cancel_task()` | Cancel a running task |
| `subscribe_to_task()` | Subscribe to task updates via SSE stream |
| `get_agent_card()` | Discover agent capabilities (public card) |
| `get_extended_agent_card()` | Get authenticated extended card (JSON-RPC) |

## Quick Start

```python
from bud import BudClient

client = BudClient(api_key="your-api-key", base_url="https://gateway.bud.studio")

# Discover agent
card = client.a2a.get_agent_card("my-agent")
print(card.name, card.description)

# Send a message
result = client.a2a.send_message("my-agent", message="Hello!")
if result.task:
    print(result.task.status.state)
    for artifact in result.task.artifacts or []:
        for part in artifact.parts:
            if part.text:
                print(part.text)

client.close()
```

## Client Setup

The A2A resource is available on `BudClient` and `AsyncBudClient` as `client.a2a`.

```python
# Default: A2A protocol v0.3
client = BudClient(api_key="your-key")
print(client.a2a.a2a_version)  # "0.3"

# Explicit v1.0
client = BudClient(api_key="your-key", a2a_version="1.0")

# Switch version at runtime
client.a2a.a2a_version = "1.0"
```

### Async Client

```python
import asyncio
from bud import AsyncBudClient

async def main():
    async with AsyncBudClient(api_key="your-key", a2a_version="1.0") as client:
        result = await client.a2a.send_message("my-agent", message="Hello!")
        print(result.task.status.state)

asyncio.run(main())
```

## Protocol Versions

The SDK supports both A2A v0.3 and v1.0. The `A2A-Version` header is sent automatically with every request.

| Aspect | v0.3 | v1.0 |
|--------|------|------|
| **Default** | Yes | No (set `a2a_version="1.0"`) |
| **Method names** | `message/send`, `tasks/get` | `SendMessage`, `GetTask` |
| **Enum values** | `"submitted"`, `"user"` | `"TASK_STATE_SUBMITTED"`, `"ROLE_USER"` |
| **Part format** | `{"kind": "text", "text": "..."}` | `{"text": "..."}` |
| **Stream events** | `kind` discriminator | Wrapper keys (`statusUpdate`, `task`) |
| **ListTasks** | Not available | Available |
| **Tenant support** | No | Yes |

The SDK handles all format differences internally. You work with the same Python types regardless of version.

## A2A Concepts

### Task Lifecycle

Tasks progress through defined states:

```
SUBMITTED → WORKING → COMPLETED (terminal)
                    → FAILED (terminal)
                    → CANCELED (terminal)
                    → REJECTED (terminal)
                    → INPUT_REQUIRED → (send follow-up) → WORKING → ...
                    → AUTH_REQUIRED → (resolve auth) → WORKING → ...
```

Terminal states: `COMPLETED`, `FAILED`, `CANCELED`, `REJECTED`

```python
from bud.models.a2a import TaskState

if task.status.state == TaskState.COMPLETED:
    print("Done!")
elif task.status.state == TaskState.INPUT_REQUIRED:
    # Agent needs more input — send follow-up with context_id
    pass
```

### Parts

Message content is carried in `Part` objects. A Part contains exactly one of:

| Field | Type | Description |
|-------|------|-------------|
| `text` | `str` | Plain text content |
| `raw` | `str` | Base64-encoded binary data |
| `url` | `str` | URL pointing to file content |
| `data` | `dict` | Arbitrary structured JSON data |

Common fields: `metadata`, `filename`, `media_type`.

### Messages and Roles

```python
from bud.models.a2a import Message, Part, Role

# Simple text (SDK wraps this automatically)
result = client.a2a.send_message("agent", message="Hello!")

# Structured message
msg = Message(
    role=Role.USER,
    parts=[Part(text="What is 2+2?")],
)
result = client.a2a.send_message("agent", message=msg)
```

### Context ID (Multi-Turn)

The `context_id` groups related messages into a conversation:

```python
r1 = client.a2a.send_message("agent", message="Convert 100 USD")
# Agent responds — use context_id for follow-up
r2 = client.a2a.send_message(
    "agent",
    message="to EUR",
    context_id=r1.task.context_id,
)
```

## Error Handling

All A2A errors raise `A2AError` with optional `code` and `data` fields:

```python
from bud.exceptions import A2AError

try:
    client.a2a.cancel_task("agent", task_id="t1")
except A2AError as e:
    print(e)         # "Task not cancelable"
    print(e.code)    # -32002
    print(e.data)    # Optional error details
```

### Common Error Codes

| Code | Name | Description |
|------|------|-------------|
| -32001 | TaskNotFound | Task ID doesn't exist |
| -32002 | TaskNotCancelable | Task already in terminal state |
| -32003 | PushNotSupported | Push notifications not supported |
| -32004 | UnsupportedOperation | Feature not available |
| -32005 | ContentTypeNotSupported | Unsupported media type |
| -32009 | VersionNotSupported | Protocol version mismatch |
| -32700 | ParseError | Invalid JSON |
| -32601 | MethodNotFound | Unknown JSON-RPC method |
| -32602 | InvalidParams | Invalid parameters |
| -32603 | InternalError | Server internal error |

## Next Steps

- [Sending Messages](send-message.md) — blocking, streaming, multi-turn conversations
- [Task Management](task-management.md) — get, list, cancel, subscribe to tasks
- [Agent Discovery](agent-discovery.md) — agent cards and capabilities
