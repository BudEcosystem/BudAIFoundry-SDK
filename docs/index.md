# BudAI SDK Documentation

Official Python SDK for the BudAI Foundry Platform.

## Table of Contents

- [Quick Start](quickstart.md)
- [Configuration & Authentication](configuration.md)
- **API Reference**
  - [Chat Completions](api/chat.md)
  - [Embeddings](api/embeddings.md)
  - [Classifications](api/classifications.md)
  - [Models](api/models.md)
- **Examples**
  - [Inference Examples](../examples/inference_example.py) - Chat, embeddings, classifications
  - [Pipeline Examples](../examples/simple_pipeline.py) - Basic pipeline usage
  - [Dapr Internal](../examples/dapr_internal.py) - Internal service authentication

## Installation

```bash
pip install bud-sdk
```

## Basic Usage

```python
from bud import BudClient

# Initialize client
client = BudClient(
    api_key="your-api-key",
    base_url="https://gateway.bud.studio"
)

# Chat completion
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.choices[0].message.content)

# Embeddings
response = client.embeddings.create(
    model="bge-m3",
    input="Hello, world!"
)
print(f"Dimensions: {len(response.data[0].embedding)}")

# Classification
response = client.classifications.create(
    model="finbert",
    input=["The market is up today"]
)
for label in response.data[0]:
    print(f"{label.label}: {label.score:.2%}")

# Clean up
client.close()
```

## Features

- **Chat Completions**: OpenAI-compatible chat API with streaming support
- **Embeddings**: Text, image, and audio embeddings with chunking and caching
- **Classifications**: Text classification with multiple models
- **Models**: List and retrieve available models

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BUD_API_KEY` | API key for authentication | - |
| `BUD_BASE_URL` | Base URL for the API | `https://gateway.bud.studio` |
| `BUD_TIMEOUT` | Request timeout in seconds | `60` |
| `BUD_MAX_RETRIES` | Maximum retry attempts | `3` |

## Support

- [GitHub Issues](https://github.com/BudEcosystem/BudAIFoundry-SDK/issues)
- [Documentation](https://docs.budecosystem.com/sdk)
