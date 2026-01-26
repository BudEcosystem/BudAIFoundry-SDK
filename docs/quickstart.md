# Quick Start Guide

Get started with the BudAI SDK in minutes.

## Installation

```bash
pip install bud-sdk
```

## Authentication

### Option 1: API Key (Recommended)

```python
from bud import BudClient

client = BudClient(api_key="your-api-key")
```

### Option 2: Environment Variables

```bash
export BUD_API_KEY="your-api-key"
export BUD_BASE_URL="https://gateway.bud.studio"
```

```python
from bud import BudClient

client = BudClient()  # Reads from environment
```

### Option 3: Configuration File

Create `~/.bud/config.toml`:

```toml
api_key = "your-api-key"
base_url = "https://gateway.bud.studio"
```

## Your First Request

### Chat Completion

```python
from bud import BudClient

client = BudClient(api_key="your-api-key")

response = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is Python?"}
    ]
)

print(response.choices[0].message.content)
client.close()
```

### Streaming Response

```python
stream = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Count to 5"}],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
```

### Text Embeddings

```python
response = client.embeddings.create(
    model="bge-m3",
    input="Hello, world!"
)

embedding = response.data[0].embedding
print(f"Embedding dimensions: {len(embedding)}")
```

### Text Classification

```python
response = client.classifications.create(
    model="finbert",
    input=["The stock market rallied today with strong gains."]
)

for label_score in response.data[0]:
    print(f"{label_score.label}: {label_score.score:.2%}")
```

## Context Manager

Use the client as a context manager for automatic cleanup:

```python
from bud import BudClient

with BudClient(api_key="your-api-key") as client:
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello!"}]
    )
    print(response.choices[0].message.content)
# Client is automatically closed
```

## Error Handling

```python
from bud import BudClient
from bud.exceptions import (
    BudError,
    AuthenticationError,
    RateLimitError,
    NotFoundError,
    ValidationError,
)

client = BudClient(api_key="your-api-key")

try:
    response = client.chat.completions.create(
        model="nonexistent-model",
        messages=[{"role": "user", "content": "Hello!"}]
    )
except AuthenticationError:
    print("Invalid API key")
except NotFoundError:
    print("Model not found")
except RateLimitError:
    print("Rate limit exceeded, please retry later")
except ValidationError as e:
    print(f"Invalid request: {e}")
except BudError as e:
    print(f"API error: {e}")
```

## Next Steps

- [Chat Completions API](api/chat.md) - Full chat API documentation
- [Embeddings API](api/embeddings.md) - Text and multimodal embeddings
- [Classifications API](api/classifications.md) - Text classification
- [Configuration](configuration.md) - Advanced configuration options

## Examples

Working code examples are available in the [examples/](../examples/) directory:

- [inference_example.py](../examples/inference_example.py) - Chat, embeddings, and classification examples
- [simple_pipeline.py](../examples/simple_pipeline.py) - Basic pipeline usage
- [dapr_internal.py](../examples/dapr_internal.py) - Internal service authentication

Run examples with:

```bash
BUD_API_KEY=your-key BUD_BASE_URL=https://gateway.bud.studio python examples/inference_example.py
```
