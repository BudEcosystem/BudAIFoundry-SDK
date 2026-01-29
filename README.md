# BudAIFoundry SDK

Official Python SDK for the BudAI Foundry Platform. Build, manage, and execute DAG-based pipelines with ease.

## Features

- **Python SDK** - Full-featured client library for the BudAI Foundry API
- **OpenAI-Compatible Inference** - Chat completions, embeddings, and classifications
- **CLI Tool** - Command-line interface for pipeline operations
- **Pipeline DSL** - Pythonic way to define DAG pipelines
- **Async Support** - Both sync and async clients available
- **Type Safety** - Full type hints and Pydantic models

## Documentation

- [Quick Start Guide](docs/quickstart.md)
- [Configuration & Authentication](docs/configuration.md)
- **API Reference**
  - [Chat Completions](docs/api/chat.md)
  - [Embeddings](docs/api/embeddings.md)
  - [Classifications](docs/api/classifications.md)
  - [Models](docs/api/models.md)

## Installation

```bash
pip install git+https://github.com/BudEcosystem/BudAIFoundry-SDK
```

## Quick Start

### Using the SDK

```python
from bud import BudClient, Pipeline, Action

# Initialize client (uses stored tokens from `bud auth login`)
client = BudClient()

# Or with explicit credentials
# client = BudClient(email="user@example.com", password="secret")

# Define a pipeline using the DSL
with Pipeline("my-pipeline") as p:
    start = Action("start", type="log").with_config(
        message="Pipeline started",
        level="info",
    )

    transform = Action("transform", type="transform").with_config(
        input="${params.data}",
        operation="uppercase",
    ).after(start)

    output = Action("output", type="set_output").with_config(
        key="result",
        value="${steps.transform.output}",
    ).after(transform)

# Create and run the pipeline
pipeline = client.pipelines.create(dag=p.to_dag(), name=p.name)
execution = client.executions.create(pipeline.id, params={"data": "hello"})

print(f"Execution: {execution.effective_id}")
print(f"Status: {execution.status}")
```

### Using the CLI

```bash
# Authenticate
bud auth login

# List available actions
bud action list

# Create a pipeline from a Python file
bud pipeline create deploy.py --name deploy-app

# Run a pipeline
bud run deploy-app --param env=prod --wait

# List executions
bud execution list --status running
```

## Authentication

The SDK supports multiple authentication methods:

### 1. CLI Login (Recommended for Development)

```bash
# Interactive login
bud auth login

# Check status
bud auth status
```

Then use the SDK without any credentials:

```python
from bud import BudClient

# Uses stored tokens from ~/.bud/tokens.json
client = BudClient()
```

### 2. Email/Password (JWT)

```python
from bud import BudClient

client = BudClient(
    email="user@example.com",
    password="your-password",
)

# Or via environment variables
# export BUD_EMAIL="user@example.com"
# export BUD_PASSWORD="your-password"
client = BudClient()
```

JWT tokens are automatically refreshed before expiry.

### 3. API Key

```python
from bud import BudClient

client = BudClient(api_key="your-api-key")

# Or via environment variable
# export BUD_API_KEY="your-api-key"
client = BudClient()
```

### 4. Dapr Token (Internal Services)

For services running inside the Bud platform with Dapr sidecar:

```python
from bud import BudClient

# Minimal - defaults to localhost:3500 with auto invoke path
client = BudClient(dapr_token="your-dapr-token")

# With user context
client = BudClient(
    dapr_token="your-dapr-token",
    user_id="user-id-to-act-as",
)

# Or via environment variables
# export BUD_DAPR_TOKEN="your-dapr-token"
# export BUD_USER_ID="user-id"
client = BudClient()
```

The SDK automatically:
- Defaults to `http://localhost:3500` (Dapr sidecar)
- Appends `/v1.0/invoke/budpipeline/method` to the URL

### Authentication Priority

1. Explicit `auth` parameter (custom AuthProvider)
2. `api_key` parameter or `BUD_API_KEY` env var
3. `dapr_token` parameter or `BUD_DAPR_TOKEN` env var
4. `email`/`password` parameters or `BUD_EMAIL`/`BUD_PASSWORD` env vars
5. Config file (`~/.bud/config.toml`)
6. Stored tokens from CLI login (`~/.bud/tokens.json`)

---

## SDK Usage

### Pipelines

```python
# List pipelines
pipelines = client.pipelines.list()

# Get a pipeline
pipeline = client.pipelines.get("pipeline-id")

# Create a pipeline
pipeline = client.pipelines.create(
    dag={"steps": [...], "edges": [...]},
    name="my-pipeline",
    description="Pipeline description",
)

# Delete a pipeline
client.pipelines.delete("pipeline-id")
```

### Executions

```python
# Run a pipeline (simple)
execution = client.executions.create(
    "pipeline-id",
    params={"key": "value"},
)

# Run with convenience method (waits for completion by default)
execution = client.executions.run(
    "pipeline-id",
    params={"input": "data"},
)

# Run with Dapr callback topics for progress events
execution = client.executions.create(
    "pipeline-id",
    params={"input_data": "value", "model_id": "model-123"},
    callback_topics=["my-progress-topic"],  # Dapr pub/sub topics
    user_id="user-123",                      # User ID for tracking
    initiator="my-service",                  # Service identifier
)

# Run ephemeral pipeline (without registering it first)
execution = client.executions.run_ephemeral(
    pipeline_definition={
        "name": "one-off-task",
        "steps": [
            {"id": "step1", "name": "Log Message", "action": "log", "params": {"message": "Hello"}},
        ],
    },
    params={"input": "data"},
)

# Get execution status
execution = client.executions.get(execution.effective_id)
print(f"Status: {execution.status}")

# Cancel an execution
client.executions.cancel(execution.effective_id)

# List executions
executions = client.executions.list(status="running")
```

#### Dapr Callback Topics

When running inside the Bud platform with Dapr, you can receive progress events via pub/sub:

```python
from bud import BudClient

# Internal service with Dapr sidecar
client = BudClient(dapr_token="your-dapr-token")

# Execute with callback - progress events published to your topic
execution = client.executions.run(
    "pipeline-id",
    params={"data": "input"},
    callback_topics=["my-service-progress"],
    initiator="my-service",
    wait=False,  # Don't block, receive updates via pub/sub
)

print(f"Execution started: {execution.effective_id}")
# Progress events will be published to "my-service-progress" topic
```

#### Ephemeral Executions

Run a pipeline definition directly without registering it first. Useful for one-off tasks, testing, or ad-hoc workflows:

```python
from bud import BudClient

client = BudClient()

# Execute an inline pipeline definition
execution = client.executions.run_ephemeral(
    pipeline_definition={
        "name": "data-transform",
        "steps": [
            {
                "id": "transform",
                "name": "Transform Input",
                "action": "transform",
                "params": {"operation": "uppercase"},
            },
        ],
    },
    params={"input": "hello world"},
    wait=True,  # Wait for completion
)

print(f"Status: {execution.status}")
print(f"Output: {execution.outputs}")
```

The ephemeral execution is tracked but the pipeline definition is not persisted. The returned execution will have `pipeline_id=None`.

### Actions

```python
# List available actions
actions = client.actions.list()

# Get action details
action = client.actions.get("log")
print(f"Parameters: {action.params}")
```

---

## Inference API

The SDK provides OpenAI-compatible inference endpoints for chat, embeddings, and classifications.

> See [examples/inference_example.py](examples/inference_example.py) for complete working examples.

### Chat Completions

Create chat completions with streaming support. [Full documentation](docs/api/chat.md)

```python
from bud import BudClient

client = BudClient(api_key="your-api-key")

# Basic chat completion
response = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ],
    temperature=0.7,
    max_tokens=100,
)
print(response.choices[0].message.content)

# Streaming
stream = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Count to 5"}],
    stream=True
)
for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

### Embeddings

Create text, image, or audio embeddings with chunking and caching support. [Full documentation](docs/api/embeddings.md)

```python
# Basic embedding
response = client.embeddings.create(
    model="bge-m3",
    input="Hello, world!"
)
print(f"Dimensions: {len(response.data[0].embedding)}")

# Batch embeddings
response = client.embeddings.create(
    model="bge-m3",
    input=["First text", "Second text", "Third text"]
)

# With caching
response = client.embeddings.create(
    model="bge-m3",
    input="Frequently requested text",
    cache_options={"enabled": "on", "max_age_s": 3600}
)

# With chunking for long documents
response = client.embeddings.create(
    model="bge-m3",
    input="Very long document...",
    chunking={"strategy": "sentence", "chunk_size": 512}
)
```

**Embedding Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `model` | `str` | Model ID (required) |
| `input` | `str \| list[str]` | Text to embed (required) |
| `encoding_format` | `str` | `"float"` or `"base64"` |
| `modality` | `str` | `"text"`, `"image"`, or `"audio"` |
| `dimensions` | `int` | Output dimensions (0 = full) |
| `priority` | `str` | `"high"`, `"normal"`, or `"low"` |
| `include_input` | `bool` | Return original text in response |
| `chunking` | `dict` | Chunking configuration |
| `cache_options` | `dict` | Cache settings |

### Classifications

Classify text using deployed classifier models. [Full documentation](docs/api/classifications.md)

```python
# Single classification
response = client.classifications.create(
    model="finbert",
    input=["The stock market rallied today with strong gains."]
)

for label_score in response.data[0]:
    print(f"{label_score.label}: {label_score.score:.2%}")
# Output: positive: 92.84%, neutral: 5.06%, negative: 2.10%

# Batch classification
response = client.classifications.create(
    model="finbert",
    input=[
        "Company reports record profits.",
        "Market crash leads to losses.",
        "Trading volume steady today."
    ],
    priority="high"
)

for i, result in enumerate(response.data):
    top = max(result, key=lambda x: x.score)
    print(f"Text {i+1}: {top.label} ({top.score:.1%})")
```

**Classification Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `input` | `list[str]` | Texts to classify (required) |
| `model` | `str` | Classifier model ID |
| `raw_scores` | `bool` | Return raw scores vs normalized |
| `priority` | `str` | `"high"`, `"normal"`, or `"low"` |

### List Models

```python
# List all available models
models = client.models.list()
for model in models.data:
    print(f"{model.id} - {model.owned_by}")

# Get specific model info
model = client.models.retrieve("gpt-4")
```

---

## Pipeline DSL

Define pipelines using Python:

```python
from bud import Pipeline, Action

with Pipeline("data-processing") as p:
    # Basic action
    start = Action("start", type="log").with_config(
        message="Starting pipeline",
        level="info",
    )

    # Action with timeout
    process = Action("process", type="transform").with_config(
        input="${params.data}",
        operation="uppercase",
    ).with_timeout(3600).after(start)

    # Action with retry
    save = Action("save", type="set_output").with_config(
        key="result",
        value="${steps.process.output}",
    ).with_retry(
        max_attempts=3,
        delay=5,
    ).after(process)

    # Conditional action
    notify = Action("notify", type="log").with_config(
        message="Processing complete",
    ).when(
        "steps.save.status == 'completed'"
    ).after(save)

# Convert to DAG for API
dag = p.to_dag()
```

### Parallel Actions

```python
from bud import Pipeline, Action

with Pipeline("parallel-example") as p:
    setup = Action("setup", type="log").with_config(message="Setup")

    # These run in parallel (no dependencies between them)
    task1 = Action("task1", type="transform").after(setup)
    task2 = Action("task2", type="transform").after(setup)
    task3 = Action("task3", type="transform").after(setup)

    # This waits for all parallel tasks
    finalize = Action("finalize", type="log").after(task1, task2, task3)
```

## CLI Reference

```
bud
├── auth
│   ├── login             Authenticate with BudAI Foundry
│   ├── logout            Remove credentials
│   ├── status            Show auth status
│   └── refresh           Refresh JWT tokens
├── pipeline
│   ├── list              List all pipelines
│   ├── describe <id>     Show pipeline details
│   ├── create <file>     Create pipeline from Python file
│   └── delete <id>       Delete a pipeline
├── run <target>          Run a pipeline
├── execution
│   ├── list              List executions
│   ├── describe <id>     Show execution details
│   └── cancel <id>       Cancel running execution
├── action
│   ├── list              List available actions
│   └── describe <type>   Show action details
├── config
│   ├── get <key>         Get config value
│   ├── set <key> <val>   Set config value
│   └── list              List all config
└── version               Show version
```

### Common Options

- `--json` / `-j` - Output in JSON format
- `--help` - Show help for any command

### Examples

```bash
# Run a pipeline file
bud run deploy.py --param image=latest

# Run by pipeline ID and wait
bud run abc123 --wait

# List failed executions
bud execution list --status failed --limit 10

# View action parameters
bud action describe model_add

# JSON output for scripting
bud pipeline list --json | jq '.[].name'
```

## Configuration

Configuration is loaded from (in order of precedence):

1. Command-line arguments
2. Environment variables
3. Config file (`~/.bud/config.toml`)
4. Defaults

### Environment Variables

```bash
# Authentication (choose one method)
export BUD_API_KEY="your-api-key"           # API key auth
export BUD_DAPR_TOKEN="dapr-token"          # Dapr auth (internal services)
export BUD_USER_ID="user-id"                # Optional: user context with Dapr
export BUD_EMAIL="user@example.com"         # JWT auth
export BUD_PASSWORD="your-password"         # JWT auth

# Client configuration
export BUD_BASE_URL="https://your-bud-instance.example.com"
export BUD_TIMEOUT="60"
export BUD_MAX_RETRIES="3"
```

### Config File

```toml
# ~/.bud/config.toml

base_url = "https://your-bud-instance.example.com"
timeout = 60
max_retries = 3

# Authentication - choose one method:

# Option 1: API Key
api_key = "your-api-key"

# Option 2: Dapr (for internal services)
# [auth]
# type = "dapr"
# dapr_token = "your-dapr-token"
# user_id = "optional-user-id"

# Option 3: JWT (email/password)
# [auth]
# type = "jwt"
# email = "user@example.com"
# password = "your-password"
```

## Error Handling

```python
from bud import BudClient
from bud.exceptions import (
    BudError,
    AuthenticationError,
    NotFoundError,
    ValidationError,
    RateLimitError,
)

client = BudClient()

try:
    pipeline = client.pipelines.get("non-existent")
except NotFoundError as e:
    print(f"Pipeline not found: {e}")
except AuthenticationError as e:
    print(f"Auth failed: {e}")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after}s")
except BudError as e:
    print(f"API error: {e}")
```

## Development

```bash
# Clone the repository
git clone https://github.com/BudEcosystem/BudAIFoundry-SDK.git
cd BudAIFoundry-SDK

# Install dependencies
uv sync --all-extras

# Install pre-commit hooks
uv run pre-commit install

# Run tests
uv run pytest

# Run linting
uv run ruff check .
uv run mypy src/

# Run all pre-commit hooks
uv run pre-commit run --all-files

# Build package
uv build
```

## License

Apache 2.0 - See [LICENSE](LICENSE) for details.
