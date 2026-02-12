# Responses API

Create responses using the OpenAI-compatible Responses endpoint with support for multi-turn conversations, tool use, and streaming.

> **Examples**: See [track_responses.py](../../examples/observability/track_responses.py) for working code examples with observability.

## Basic Usage

```python
from bud import BudClient

client = BudClient(api_key="your-api-key")

response = client.responses.create(
    model="gpt-4.1",
    input="What is Python?"
)

print(response.output_text)
```

## Method Signature

```python
client.responses.create(
    *,
    model: str | None = None,
    input: str | list[dict[str, Any]] | None = None,
    stream: bool = False,
    instructions: str | None = None,
    previous_response_id: str | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    max_output_tokens: int | None = None,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | dict[str, Any] | None = None,
    parallel_tool_calls: bool | None = None,
    reasoning: dict[str, Any] | None = None,
    metadata: dict[str, str] | None = None,
    user: str | None = None,
    prompt: dict[str, Any] | None = None,
    store: bool | None = None,
    background: bool | None = None,
    service_tier: str | None = None,
    text: dict[str, Any] | None = None,
    truncation: str | None = None,
    include: list[str] | None = None,
) -> Response | ResponseStream
```

## Parameters

### Required Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `model` | `str` | Model ID (e.g., `"gpt-4.1"`). Required unless `prompt` is provided |

> **Note:** At least one of `model` or `prompt` must be provided.

### Optional Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `input` | `str \| list[dict]` | `None` | Text string or list of input messages |
| `stream` | `bool` | `False` | Enable streaming response |
| `instructions` | `str` | `None` | System instructions for the model |
| `previous_response_id` | `str` | `None` | ID of a previous response for multi-turn conversations |
| `temperature` | `float` | `None` | Sampling temperature (0-2) |
| `top_p` | `float` | `None` | Nucleus sampling probability |
| `max_output_tokens` | `int` | `None` | Maximum tokens to generate |
| `tools` | `list[dict]` | `None` | List of tools the model may call |
| `tool_choice` | `str \| dict` | `None` | Controls which tool is called |
| `parallel_tool_calls` | `bool` | `None` | Allow parallel tool calls |
| `reasoning` | `dict` | `None` | Reasoning configuration |
| `metadata` | `dict[str, str]` | `None` | Key-value metadata attached to the response |
| `user` | `str` | `None` | Unique user identifier |
| `prompt` | `dict` | `None` | Stored prompt configuration (alternative to model + input) |
| `store` | `bool` | `None` | Whether to store the response |
| `background` | `bool` | `None` | Whether to run in the background |
| `service_tier` | `str` | `None` | Service tier for the request |
| `text` | `dict` | `None` | Text generation configuration |
| `truncation` | `str` | `None` | Truncation strategy |
| `include` | `list[str]` | `None` | Additional fields to include in response |

### Parameter Details

#### `input`

The input can be a simple string or a list of message objects:

```python
# Simple string
response = client.responses.create(model="gpt-4.1", input="Hello!")

# List of messages
response = client.responses.create(
    model="gpt-4.1",
    input=[
        {"role": "user", "content": "What is Python?"},
    ]
)
```

#### `prompt`

Use a stored prompt configuration instead of specifying `model` and `input` directly:

```python
response = client.responses.create(
    prompt={
        "id": "my-prompt-id",
        "version": "1.0",
        "variables": {"topic": "Python"}
    }
)
```

#### `previous_response_id`

Chain responses for multi-turn conversations without resending the full history:

```python
r1 = client.responses.create(model="gpt-4.1", input="What is Python?")
r2 = client.responses.create(
    model="gpt-4.1",
    input="What are its main features?",
    previous_response_id=r1.id,
)
```

#### `reasoning`

Configure the model's reasoning behavior:

```python
response = client.responses.create(
    model="gpt-4.1",
    input="Solve this step by step: 2x + 5 = 15",
    reasoning={"effort": "high"},
)
```

#### `tools`

Define tools the model can call:

```python
response = client.responses.create(
    model="gpt-4.1",
    input="What's the weather in London?",
    tools=[
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"}
                    },
                    "required": ["location"]
                }
            }
        }
    ],
)
```

## Response Object

The non-streaming response is an `openai.types.responses.Response` object.

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Unique response ID |
| `object` | `str` | Always `"response"` |
| `model` | `str` | Model used |
| `status` | `str` | Response status |
| `output` | `list` | List of output items |
| `output_text` | `str` | Convenience property — concatenated text output |
| `usage` | `Usage` | Token usage information |
| `created_at` | `datetime` | Creation timestamp |
| `temperature` | `float \| None` | Temperature used |
| `top_p` | `float \| None` | Top-p used |
| `max_output_tokens` | `int \| None` | Max output tokens used |
| `metadata` | `dict \| None` | Attached metadata |

### Usage Fields

| Field | Type | Description |
|-------|------|-------------|
| `input_tokens` | `int` | Number of input tokens |
| `output_tokens` | `int` | Number of output tokens |
| `total_tokens` | `int` | Total tokens |

## Streaming

### Basic Streaming

```python
stream = client.responses.create(
    model="gpt-4.1",
    input="Write a poem about Python",
    stream=True,
)

for event in stream:
    if event.type == "response.output_text.delta":
        print(event.delta, end="", flush=True)
print()
```

### ResponseStream

The synchronous stream object returned when `stream=True`.

| Method / Property | Description |
|-------------------|-------------|
| `__iter__()` | Iterate over `ResponseStreamEvent` objects |
| `close()` | Close the stream and release resources |
| `completed_response` | The full `Response` object from the `response.completed` event (available after iteration) |
| `__enter__()` / `__exit__()` | Context manager support |

```python
stream = client.responses.create(model="gpt-4.1", input="Hello", stream=True)

with stream as s:
    for event in s:
        if event.type == "response.output_text.delta":
            print(event.delta, end="")

# Access the completed response after iteration
print(stream.completed_response.usage)
```

### AsyncResponseStream

The async version for use with `AsyncBudClient`.

| Method / Property | Description |
|-------------------|-------------|
| `__aiter__()` | Async iterate over events |
| `aclose()` | Close the stream asynchronously |
| `completed_response` | Full `Response` object after iteration |
| `__aenter__()` / `__aexit__()` | Async context manager support |

### Common Event Types

| Event Type | Description |
|------------|-------------|
| `response.created` | Response object created |
| `response.in_progress` | Response generation in progress |
| `response.output_text.delta` | Incremental text output (access via `event.delta`) |
| `response.output_text.done` | Text output complete |
| `response.content_part.added` | New content part added |
| `response.content_part.done` | Content part complete |
| `response.output_item.added` | New output item added |
| `response.output_item.done` | Output item complete |
| `response.completed` | Response complete (contains full `Response` object) |
| `response.failed` | Response generation failed |

## Examples

### Simple Text Response

```python
response = client.responses.create(
    model="gpt-4.1",
    input="Explain quantum computing in one sentence."
)
print(response.output_text)
```

### Streaming Response

```python
stream = client.responses.create(
    model="gpt-4.1",
    input="Count to 10",
    stream=True,
)

for event in stream:
    if event.type == "response.output_text.delta":
        print(event.delta, end="", flush=True)
print()
```

### Stored Prompt

```python
response = client.responses.create(
    prompt={
        "id": "summarize-v2",
        "version": "1.0",
        "variables": {"text": "Long document here..."}
    }
)
print(response.output_text)
```

### Multi-turn Conversation

```python
# First turn
r1 = client.responses.create(
    model="gpt-4.1",
    input="My name is Alice."
)

# Second turn — references the first
r2 = client.responses.create(
    model="gpt-4.1",
    input="What is my name?",
    previous_response_id=r1.id,
)
print(r2.output_text)  # "Your name is Alice."
```

### With Instructions

```python
response = client.responses.create(
    model="gpt-4.1",
    input="Tell me about Python",
    instructions="You are a concise technical writer. Keep responses under 50 words.",
    temperature=0.3,
)
```

### With Observability

```python
from bud.observability import configure, track_responses, shutdown

configure(client=client, service_name="my-service")
track_responses(client)

response = client.responses.create(
    model="gpt-4.1",
    input="Hello!"
)
# Automatically creates an OTel span with request/response attributes

shutdown()
```

## Error Handling

```python
from bud.exceptions import BudError, AuthenticationError, NotFoundError

try:
    response = client.responses.create(
        model="gpt-4.1",
        input="Hello!"
    )
except ValueError as e:
    # Neither model nor prompt provided
    print(f"Validation error: {e}")
except AuthenticationError:
    print("Invalid API key")
except NotFoundError:
    print("Model not found")
except BudError as e:
    print(f"API error: {e}")
```

## Async Usage

```python
import asyncio
from bud import AsyncBudClient

async def main():
    async with AsyncBudClient(api_key="your-api-key") as client:
        # Non-streaming
        response = await client.responses.create(
            model="gpt-4.1",
            input="What is Python?"
        )
        print(response.output_text)

        # Streaming
        stream = await client.responses.create(
            model="gpt-4.1",
            input="Count to 5",
            stream=True,
        )
        async for event in stream:
            if event.type == "response.output_text.delta":
                print(event.delta, end="", flush=True)

asyncio.run(main())
```

## Best Practices

- **Use `previous_response_id` for multi-turn** — Avoids resending the full conversation history and lets the server manage context
- **Use `instructions` instead of system messages** — The Responses API uses `instructions` for system-level guidance
- **Access `completed_response` after streaming** — Contains the full response with usage data
- **Use stored prompts for reusable templates** — The `prompt` parameter supports version-controlled prompt configurations
- **Add observability** — Use `track_responses()` to automatically trace all Responses API calls with OpenTelemetry. See [Auto-Instrumentation](../observability/auto-instrumentation.md)
