# Configuration & Authentication

## Client Initialization

```python
from bud import BudClient

client = BudClient(
    api_key="your-api-key",           # API key for authentication
    base_url="https://gateway.bud.studio",  # API base URL
    timeout=60.0,                      # Request timeout in seconds
    max_retries=3,                     # Maximum retry attempts
    verify_ssl=True,                   # SSL certificate verification
)
```

## Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `str` | `None` | API key for token-based authentication |
| `email` | `str` | `None` | Email for JWT authentication |
| `password` | `str` | `None` | Password for JWT authentication |
| `dapr_token` | `str` | `None` | Dapr token for internal service auth |
| `user_id` | `str` | `None` | User ID for Dapr authentication |
| `auth` | `AuthProvider` | `None` | Custom authentication provider |
| `base_url` | `str` | `None` | API base URL |
| `app_url` | `str` | `None` | App service URL for telemetry queries |
| `timeout` | `float` | `60.0` | Request timeout in seconds |
| `app_timeout` | `float` | `30.0` | HTTP timeout for app service requests |
| `max_retries` | `int` | `3` | Maximum retry attempts |
| `verify_ssl` | `bool` | `True` | SSL certificate verification |

## Authentication Methods

### 1. API Key Authentication (Recommended)

```python
client = BudClient(api_key="your-api-key")
```

### 2. Email/Password (JWT)

```python
client = BudClient(
    email="user@example.com",
    password="your-password"
)
```

### 3. Dapr Token (Internal Services)

```python
client = BudClient(
    dapr_token="your-dapr-token",
    user_id="user-123"  # Optional
)
```

### 4. Custom Auth Provider

```python
from bud.auth import APIKeyAuth, JWTAuth, DaprAuth

# API Key
auth = APIKeyAuth(api_key="your-api-key")
client = BudClient(auth=auth)

# JWT
auth = JWTAuth(email="user@example.com", password="secret")
client = BudClient(auth=auth)

# Dapr
auth = DaprAuth(token="dapr-token", user_id="user-123")
client = BudClient(auth=auth)
```

## Environment Variables

The SDK reads configuration from environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `BUD_API_KEY` | API key for authentication | - |
| `BUD_BASE_URL` | Base URL for the API | `https://gateway.bud.studio` |
| `BUD_TIMEOUT` | Request timeout in seconds | `60` |
| `BUD_MAX_RETRIES` | Maximum retry attempts | `3` |
| `BUD_EMAIL` | Email for JWT auth | - |
| `BUD_PASSWORD` | Password for JWT auth | - |
| `BUD_DAPR_TOKEN` | Dapr token | - |
| `BUD_USER_ID` | User ID for Dapr auth | - |

```bash
export BUD_API_KEY="your-api-key"
export BUD_BASE_URL="https://gateway.bud.studio"
```

```python
from bud import BudClient

# Automatically reads from environment
client = BudClient()
```

## Configuration File

Create a configuration file at `~/.bud/config.toml`:

```toml
# API Key authentication
api_key = "your-api-key"

# Server settings
base_url = "https://gateway.bud.studio"
timeout = 60
max_retries = 3
verify_ssl = true

# Alternative: JWT authentication
[auth]
type = "jwt"
email = "user@example.com"
password = "your-password"

# Alternative: Dapr authentication
[auth]
type = "dapr"
dapr_token = "your-dapr-token"
user_id = "user-123"
```

## Authentication Priority

The SDK resolves authentication in the following order (highest to lowest priority):

1. Explicit `auth` parameter
2. Explicit credential parameters (`api_key`, `dapr_token`, `email`/`password`)
3. Environment variables
4. Configuration file (`~/.bud/config.toml`)
5. Stored tokens from CLI login (`~/.bud/tokens.json`)

## Async Client

For asynchronous applications:

```python
import asyncio
from bud import AsyncBudClient

async def main():
    async with AsyncBudClient(api_key="your-api-key") as client:
        pipelines = await client.pipelines.list()
        print(pipelines)

asyncio.run(main())
```

## Resource Cleanup

Always close the client when done:

```python
# Option 1: Explicit close
client = BudClient(api_key="your-api-key")
try:
    # Use client...
finally:
    client.close()

# Option 2: Context manager (recommended)
with BudClient(api_key="your-api-key") as client:
    # Use client...
# Automatically closed
```

## Retry Behavior

The SDK automatically retries failed requests for:
- Network errors
- 5xx server errors
- 429 rate limit errors (with exponential backoff)

Configure retry behavior:

```python
client = BudClient(
    api_key="your-api-key",
    max_retries=5,  # Retry up to 5 times
    timeout=120.0,  # 2 minute timeout
)
```

## SSL Verification

For development environments with self-signed certificates:

```python
client = BudClient(
    api_key="your-api-key",
    verify_ssl=False  # Disable SSL verification (not recommended for production)
)
```

## Observability Configuration

The SDK includes built-in OpenTelemetry observability. For full documentation, see the [Observability Guide](observability/index.md).

### OTel Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BUD_OTEL_MODE` | Observability mode (`auto`, `create`, `attach`, `internal`, `disabled`) | `auto` |
| `BUD_OTEL_ENABLED` | Enable or disable observability (`true`, `false`) | `true` |
| `BUD_OTEL_SERVICE_NAME` | OTel service name (falls back to `OTEL_SERVICE_NAME`) | `bud-sdk-client` |

### Quick Setup

```python
from bud import BudClient
from bud.observability import configure, shutdown

client = BudClient(api_key="your-api-key")
configure(client=client, service_name="my-service")

# ... use client ...

shutdown()
```

## Telemetry Query Configuration

The [Telemetry Query API](api/telemetry.md) connects to the BudAI app service (not the gateway). Configure `app_url` to enable it:

```python
client = BudClient(
    api_key="your-api-key",
    base_url="https://gateway.bud.studio",
    app_url="https://app.bud.studio",
    app_timeout=30.0,  # Optional: timeout for app service requests
)

result = client.observability.query(prompt_id="my-prompt")
```

The `app_url` can also be set via the `BUD_APP_URL` environment variable:

```bash
export BUD_APP_URL="https://app.bud.studio"
```
