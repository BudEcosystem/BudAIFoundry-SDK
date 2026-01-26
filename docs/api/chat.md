# Chat Completions API

Create chat completions using OpenAI-compatible models.

> **Examples**: See [inference_example.py](../../examples/inference_example.py) for working code examples.

## Basic Usage

```python
from bud import BudClient

client = BudClient(api_key="your-api-key")

response = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ]
)

print(response.choices[0].message.content)
```

## Method Signature

```python
client.chat.completions.create(
    *,
    model: str,
    messages: list[dict],
    stream: bool = False,
    temperature: float | None = None,
    top_p: float | None = None,
    max_tokens: int | None = None,
    stop: str | list[str] | None = None,
    presence_penalty: float | None = None,
    frequency_penalty: float | None = None,
    user: str | None = None,
    tools: list[dict] | None = None,
    tool_choice: str | dict | None = None,
) -> ChatCompletion | Stream[ChatCompletionChunk]
```

## Parameters

### Required Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `model` | `str` | ID of the model to use (e.g., `"gpt-4"`, `"gpt-3.5-turbo"`) |
| `messages` | `list[dict]` | List of messages in the conversation |

### Optional Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `stream` | `bool` | `False` | Enable streaming response |
| `temperature` | `float` | `1.0` | Sampling temperature (0.0 to 2.0) |
| `top_p` | `float` | `1.0` | Nucleus sampling probability (0.0 to 1.0) |
| `max_tokens` | `int` | Model default | Maximum tokens to generate |
| `stop` | `str \| list[str]` | `None` | Stop sequences |
| `presence_penalty` | `float` | `0.0` | Presence penalty (-2.0 to 2.0) |
| `frequency_penalty` | `float` | `0.0` | Frequency penalty (-2.0 to 2.0) |
| `user` | `str` | `None` | Unique user identifier |
| `tools` | `list[dict]` | `None` | List of tools the model may call |
| `tool_choice` | `str \| dict` | `None` | Controls which tool is called |

### Parameter Details

#### `temperature`
Controls randomness in the output:
- `0.0`: Deterministic, most likely token always chosen
- `0.3-0.7`: Balanced creativity and consistency
- `1.0-2.0`: More random and creative

#### `top_p`
Nucleus sampling - considers tokens with cumulative probability:
- `0.1`: Only top 10% probability mass
- `0.9`: Top 90% probability mass
- `1.0`: All tokens considered

#### `stop`
Sequences that stop generation:
```python
stop="DONE"           # Single stop sequence
stop=["END", "STOP"]  # Multiple stop sequences
```

#### `presence_penalty` / `frequency_penalty`
- Positive values: Discourage repetition
- Negative values: Encourage repetition
- Range: -2.0 to 2.0

## Message Format

### Message Roles

| Role | Description |
|------|-------------|
| `system` | System instructions that guide the model's behavior |
| `user` | Messages from the user |
| `assistant` | Previous responses from the assistant |
| `tool` | Results from tool calls |

### Message Structure

```python
messages = [
    {
        "role": "system",
        "content": "You are a helpful assistant."
    },
    {
        "role": "user",
        "content": "What is Python?"
    },
    {
        "role": "assistant",
        "content": "Python is a programming language..."
    },
    {
        "role": "user",
        "content": "Tell me more."
    }
]
```

### Tool Call Messages

```python
# Assistant response with tool call
{
    "role": "assistant",
    "content": None,
    "tool_calls": [
        {
            "id": "call_abc123",
            "type": "function",
            "function": {
                "name": "get_weather",
                "arguments": '{"location": "London"}'
            }
        }
    ]
}

# Tool result
{
    "role": "tool",
    "tool_call_id": "call_abc123",
    "content": '{"temperature": 20, "condition": "sunny"}'
}
```

## Response Object

### ChatCompletion

```python
class ChatCompletion:
    id: str                          # Unique response ID
    object: str                      # Always "chat.completion"
    created: int                     # Unix timestamp
    model: str                       # Model used
    choices: list[ChatCompletionChoice]
    usage: Usage | None
    system_fingerprint: str | None
```

### ChatCompletionChoice

```python
class ChatCompletionChoice:
    index: int                       # Choice index
    message: ChatMessage             # Response message
    finish_reason: str | None        # "stop", "length", "tool_calls", "content_filter"
```

### ChatMessage

```python
class ChatMessage:
    role: str                        # "assistant"
    content: str | None              # Response content
    name: str | None                 # Optional name
    tool_call_id: str | None         # For tool responses
    tool_calls: list[dict] | None    # Tool calls made
```

### Usage

```python
class Usage:
    prompt_tokens: int               # Input tokens
    completion_tokens: int           # Output tokens
    total_tokens: int                # Total tokens
```

### Finish Reasons

| Value | Description |
|-------|-------------|
| `stop` | Natural end or stop sequence reached |
| `length` | Maximum tokens reached |
| `tool_calls` | Model wants to call a tool |
| `content_filter` | Content filtered |

## Streaming

Enable streaming for real-time responses:

```python
stream = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Count to 10"}],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
print()  # Newline at end
```

### Streaming Response Object

```python
class ChatCompletionChunk:
    id: str
    object: str                      # "chat.completion.chunk"
    created: int
    model: str
    choices: list[ChatCompletionChunkChoice]

class ChatCompletionChunkChoice:
    index: int
    delta: ChatCompletionDelta       # Incremental content
    finish_reason: str | None

class ChatCompletionDelta:
    role: str | None                 # Only in first chunk
    content: str | None              # Incremental content
    tool_calls: list[dict] | None
```

## Tool Calling

### Define Tools

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City name"
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"]
                    }
                },
                "required": ["location"]
            }
        }
    }
]
```

### Tool Choice Options

```python
# Let the model decide
tool_choice="auto"

# Force a specific tool
tool_choice={"type": "function", "function": {"name": "get_weather"}}

# Force any tool
tool_choice="required"

# Disable tools
tool_choice="none"
```

### Complete Tool Calling Example

```python
import json

# Initial request
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "What's the weather in London?"}],
    tools=tools
)

message = response.choices[0].message

if message.tool_calls:
    # Process tool calls
    tool_results = []
    for tool_call in message.tool_calls:
        func_name = tool_call["function"]["name"]
        func_args = json.loads(tool_call["function"]["arguments"])

        # Execute the function (your implementation)
        result = get_weather(**func_args)

        tool_results.append({
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "content": json.dumps(result)
        })

    # Continue conversation with tool results
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "user", "content": "What's the weather in London?"},
            message.model_dump(),  # Assistant's tool call
            *tool_results          # Tool results
        ],
        tools=tools
    )

    print(response.choices[0].message.content)
```

## Examples

### Multi-turn Conversation

```python
messages = [
    {"role": "system", "content": "You are a helpful math tutor."}
]

while True:
    user_input = input("You: ")
    if user_input.lower() == "quit":
        break

    messages.append({"role": "user", "content": user_input})

    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages
    )

    assistant_message = response.choices[0].message.content
    print(f"Assistant: {assistant_message}")

    messages.append({"role": "assistant", "content": assistant_message})
```

### JSON Mode

```python
response = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {
            "role": "system",
            "content": "You are a JSON generator. Always respond with valid JSON."
        },
        {
            "role": "user",
            "content": "Generate a user profile with name, age, and email."
        }
    ],
    temperature=0.0
)

import json
data = json.loads(response.choices[0].message.content)
```

### With All Options

```python
response = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": "You are a creative writer."},
        {"role": "user", "content": "Write a haiku about programming."}
    ],
    temperature=0.8,
    top_p=0.95,
    max_tokens=100,
    stop=["\n\n"],
    presence_penalty=0.5,
    frequency_penalty=0.5,
    user="user-123"
)
```

## Limits

- Maximum messages: 1000 per request
- Maximum message content: 1,000,000 characters
