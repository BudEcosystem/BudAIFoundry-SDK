# Auto-Instrumentation

Automatic OpenTelemetry tracing for BudAI SDK inference calls.

> **Examples**: See [track_inference.py](../../examples/observability/track_inference.py) and [track_responses.py](../../examples/observability/track_responses.py) for working code examples.

## track_chat_completions()

Instruments `client.chat.completions.create()` with OTel spans. Works with both streaming and non-streaming calls.

### Basic Usage

```python
from bud import BudClient
from bud.observability import configure, track_chat_completions, shutdown

client = BudClient(api_key="your-api-key")
configure(client=client, service_name="my-service")
track_chat_completions(client)

response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.choices[0].message.content)
shutdown()
```

### Function Signature

```python
from bud.observability import track_chat_completions

track_chat_completions(
    client: BudClient,
    *,
    capture_input: bool | list[str] = True,
    capture_output: bool | list[str] = True,
    span_name: str = "chat",
) -> BudClient
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `client` | `BudClient` | — | The client instance to instrument |
| `capture_input` | `bool \| list[str]` | `True` | Controls which request fields are recorded as span attributes |
| `capture_output` | `bool \| list[str]` | `True` | Controls which response fields are recorded as span attributes |
| `span_name` | `str` | `"chat"` | Base span name. Streaming calls use `"{span_name}.stream"` |

**Returns:** The same `client` object (mutated in place).

### capture_input

Controls which request keyword arguments are recorded on the span.

| Value | Behavior |
|-------|----------|
| `True` | Capture all safe fields (default): `model`, `messages`, `temperature`, `top_p`, `max_tokens`, `stop`, `presence_penalty`, `frequency_penalty`, `user`, `tools`, `tool_choice` |
| `False` | Capture nothing |
| `list[str]` | Capture exactly the listed fields |

### capture_output

Controls which response fields are recorded on the span.

| Value | Behavior |
|-------|----------|
| `True` | Capture all safe fields (default): `id`, `object`, `model`, `created`, `choices`, `usage`, `system_fingerprint` |
| `False` | Capture nothing |
| `list[str]` | Capture exactly the listed fields |

### Span Attributes

#### Always Set

| Attribute | Description |
|-----------|-------------|
| `gen_ai.system` | Always `"bud"` |
| `bud.inference.operation` | Always `"chat"` |
| `bud.inference.stream` | `true` or `false` |

#### Request Attributes (when captured)

| Attribute | Source Field |
|-----------|-------------|
| `gen_ai.request.model` | `model` |
| `gen_ai.request.temperature` | `temperature` |
| `gen_ai.request.top_p` | `top_p` |
| `gen_ai.request.max_tokens` | `max_tokens` |
| `bud.inference.request.messages` | `messages` (JSON) |
| `bud.inference.request.tools` | `tools` (JSON) |
| `bud.inference.request.user` | `user` |

#### Response Attributes (when captured)

| Attribute | Source Field |
|-----------|-------------|
| `gen_ai.response.id` | `id` |
| `gen_ai.response.model` | `model` |
| `gen_ai.response.created` | `created` |
| `gen_ai.response.system_fingerprint` | `system_fingerprint` |
| `gen_ai.response.object` | `object` |
| `gen_ai.usage.input_tokens` | `usage.prompt_tokens` |
| `gen_ai.usage.output_tokens` | `usage.completion_tokens` |
| `gen_ai.usage.total_tokens` | `usage.total_tokens` |
| `bud.inference.response.choices` | `choices` (JSON) |

#### Streaming Attributes

| Attribute | Description |
|-----------|-------------|
| `bud.inference.ttft_ms` | Time-to-first-token in milliseconds |
| `bud.inference.chunks` | Number of chunks received |
| `bud.inference.stream_completed` | Whether the stream completed fully |

### Examples

#### Non-streaming

```python
track_chat_completions(client)

response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "What is Python?"}]
)
# Span created: "chat" with request + response attributes
```

#### Streaming with TTFT

```python
track_chat_completions(client)

stream = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Count to 5"}],
    stream=True,
)
for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
# Span created: "chat.stream" with TTFT, chunk count, and aggregated response
```

#### Field selection for PII control

```python
# Only capture model and temperature from requests, id and usage from responses
track_chat_completions(
    client,
    capture_input=["model", "temperature"],
    capture_output=["id", "usage"],
)
```

#### Capture nothing

```python
track_chat_completions(client, capture_input=False, capture_output=False)
# Only always-on attributes (gen_ai.system, bud.inference.operation, bud.inference.stream)
```

#### Nesting with @track

```python
from bud.observability import track

@track(name="ask-question", type="chain")
def ask(client, question):
    return client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": question}],
    )

track_chat_completions(client)
result = ask(client, "What is 2+2?")
# Creates parent span "ask-question" with child span "chat"
```

## track_responses()

Instruments `client.responses.create()` with OTel spans. Same structure as `track_chat_completions()` with additional attributes for the Responses API.

### Basic Usage

```python
from bud import BudClient
from bud.observability import configure, track_responses, shutdown

client = BudClient(api_key="your-api-key")
configure(client=client, service_name="my-service")
track_responses(client)

response = client.responses.create(
    model="gpt-4.1",
    input="What is Python?"
)
print(response.output_text)
shutdown()
```

### Function Signature

```python
from bud.observability import track_responses

track_responses(
    client: BudClient,
    *,
    capture_input: bool | list[str] = True,
    capture_output: bool | list[str] = True,
    span_name: str = "responses",
) -> BudClient
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `client` | `BudClient` | — | The client instance to instrument |
| `capture_input` | `bool \| list[str]` | `True` | Controls which request fields are recorded as span attributes |
| `capture_output` | `bool \| list[str]` | `True` | Controls which response fields are recorded as span attributes |
| `span_name` | `str` | `"responses"` | Base span name. Streaming calls use `"{span_name}.stream"` |

**Returns:** The same `client` object (mutated in place).

### Span Attributes

#### Always Set

| Attribute | Description |
|-----------|-------------|
| `gen_ai.system` | Always `"bud"` |
| `bud.inference.operation` | Always `"responses"` |
| `gen_ai.operation.name` | Always `"responses"` |
| `bud.inference.stream` | `true` or `false` |
| `gen_ai.conversation.id` | Set to `previous_response_id` when present |

#### Prompt Decomposition

When the `prompt` parameter is a dict, the tracker extracts sub-fields:

| Attribute | Source |
|-----------|--------|
| `gen_ai.prompt.id` | `prompt["id"]` |
| `gen_ai.prompt.version` | `prompt["version"]` |
| `gen_ai.prompt.variables` | `prompt["variables"]` (JSON) |

#### Streaming Attributes

Same as `track_chat_completions()`: `bud.inference.ttft_ms`, `bud.inference.chunks`, `bud.inference.stream_completed`.

### Examples

#### Non-streaming

```python
track_responses(client)

response = client.responses.create(
    model="gpt-4.1",
    input="Explain quantum computing"
)
# Span created: "responses" with all captured attributes
```

#### Streaming

```python
track_responses(client)

stream = client.responses.create(
    model="gpt-4.1",
    input="Write a poem about Python",
    stream=True,
)
for event in stream:
    if event.type == "response.output_text.delta":
        print(event.delta, end="", flush=True)
# Span created: "responses.stream" with TTFT and chunk count
```

#### Multi-turn conversation

```python
track_responses(client)

r1 = client.responses.create(model="gpt-4.1", input="What is Python?")
# Span: conversation.id not set

r2 = client.responses.create(
    model="gpt-4.1",
    input="What are its main features?",
    previous_response_id=r1.id,
)
# Span: gen_ai.conversation.id = r1.id
```

#### Custom span name and field selection

```python
track_responses(
    client,
    span_name="my-responses",
    capture_input=["model", "input"],
    capture_output=["id", "usage"],
)
```

## Idempotency

Both `track_chat_completions()` and `track_responses()` are safe to call multiple times on the same client. Subsequent calls are no-ops:

```python
track_chat_completions(client)
track_chat_completions(client)  # No-op, already instrumented
```

## Error Handling

Errors during an instrumented call are recorded on the span with `StatusCode.ERROR` and then re-raised. The span is always properly ended and the context token detached:

```python
track_chat_completions(client)

try:
    client.chat.completions.create(
        model="nonexistent-model",
        messages=[{"role": "user", "content": "Hello!"}]
    )
except Exception as e:
    print(f"Error: {e}")
    # Span still created with error status and exception recorded
```

## Best Practices

- **Call `configure()` before `track_*()`** — Instrumentation is a no-op until observability is configured
- **Use `capture_input`/`capture_output` for PII control** — Pass `False` or a field list to avoid recording sensitive data like message contents
- **Call `shutdown()` at exit** — Ensures all pending spans are flushed to the collector
- **Combine with `@track`** — Wrap your application functions with `@track` to create parent spans that contain the auto-instrumented inference spans as children
