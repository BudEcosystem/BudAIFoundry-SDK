# BudAI SDK Documentation

Official Python SDK for the BudAI Foundry Platform.

## Table of Contents

- [Quick Start](quickstart.md)
- [Configuration & Authentication](configuration.md)
- **API Reference**
  - [Chat Completions](api/chat.md)
  - [Responses](api/responses.md)
  - [Embeddings](api/embeddings.md)
  - [Classifications](api/classifications.md)
  - [Models](api/models.md)
  - [Telemetry Query](api/telemetry.md)
- **Observability**
  - [Overview & Setup](observability/index.md)
  - [Auto-Instrumentation](observability/auto-instrumentation.md)
  - [@track Decorator](observability/track-decorator.md)
  - [Advanced](observability/advanced.md)
- **Examples**
  - [Inference Examples](../examples/inference_example.py) - Chat, embeddings, classifications
  - [Pipeline Examples](../examples/simple_pipeline.py) - Basic pipeline usage
  - [Dapr Internal](../examples/dapr_internal.py) - Internal service authentication
  - [Observability Examples](../examples/observability/) - Tracing, metrics, and telemetry queries

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

# Responses API (using a stored prompt)
response = client.responses.create(
    prompt={
        "id": "summarize-v2",
        "version": "1.0",
        "variables": {"text": "Quantum computing uses qubits..."}
    }
)
print(response.output_text)

# Clean up
client.close()
```

## Features

- **Chat Completions**: OpenAI-compatible chat API with streaming support
- **Responses API**: OpenAI-compatible responses endpoint with multi-turn conversations and streaming
- **Embeddings**: Text, image, and audio embeddings with chunking and caching
- **Classifications**: Text classification with multiple models
- **Models**: List and retrieve available models
- **Observability**: OpenTelemetry-native tracing, metrics, and logging with auto-instrumentation
- **Telemetry Query**: Query collected span data with filtering, pagination, and trace tree support

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BUD_API_KEY` | API key for authentication | - |
| `BUD_BASE_URL` | Base URL for the API | `https://gateway.bud.studio` |
| `BUD_APP_URL` | App service URL for telemetry queries | - |
| `BUD_TIMEOUT` | Request timeout in seconds | `60` |
| `BUD_MAX_RETRIES` | Maximum retry attempts | `3` |
| `BUD_OTEL_MODE` | Observability mode (`auto`, `create`, `attach`, `disabled`) | `auto` |
| `BUD_OTEL_SERVICE_NAME` | OTel service name | `bud-sdk-client` |
| `BUD_OTEL_ENABLED` | Enable or disable observability | `true` |

## Support

- [GitHub Issues](https://github.com/BudEcosystem/BudAIFoundry-SDK/issues)
- [Documentation](https://docs.budecosystem.com/sdk)
