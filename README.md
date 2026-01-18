# BudAIFoundry SDK

Official Python SDK for the BudAI Foundry Platform. Build, manage, and execute DAG-based pipelines with ease.

## Features

- **Python SDK** - Full-featured client library for the BudAI Foundry API
- **CLI Tool** - Command-line interface for pipeline operations
- **Pipeline DSL** - Pythonic way to define DAG pipelines
- **Async Support** - Both sync and async clients available
- **Type Safety** - Full type hints and Pydantic models

## Installation

```bash
pip install bud-sdk
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv add bud-sdk
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
# Run a pipeline
execution = client.executions.create(
    "pipeline-id",
    params={"key": "value"},
)

# Get execution status
execution = client.executions.get(execution.effective_id)
print(f"Status: {execution.status}")

# Cancel an execution
client.executions.cancel(execution.effective_id)

# List executions
executions = client.executions.list(status="running")
```

### Actions

```python
# List available actions
actions = client.actions.list()

# Get action details
action = client.actions.get("log")
print(f"Parameters: {action.params}")
```

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
