# Observability

OpenTelemetry-native tracing, metrics, and logging for the BudAI SDK.

The observability module provides three levels of instrumentation:

| Level | Function / Decorator | Description | Guide |
|-------|---------------------|-------------|-------|
| Auto-instrumentation | `track_chat_completions()`, `track_responses()` | One-call patching of SDK methods | [Auto-Instrumentation](auto-instrumentation.md) |
| Declarative tracing | `@track` | Decorator for your own functions | [@track Decorator](track-decorator.md) |
| Manual spans & metrics | `get_tracer()`, `get_meter()` | Full OTel API access | [Advanced](advanced.md) |

## Installation

OpenTelemetry is a mandatory dependency of the SDK — no extras are needed for core functionality:

```bash
pip install bud-sdk
```

For framework integrations, install the relevant extras:

```bash
pip install bud-sdk[observability-fastapi]   # FastAPI auto-instrumentation
pip install bud-sdk[observability-httpx]      # httpx auto-instrumentation
```

## Quick Start

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

## configure()

The main entry point for setting up observability. Safe to call even if OpenTelemetry dependencies are missing.

### Function Signature

```python
from bud.observability import configure

configure(
    api_key: str | None = None,
    *,
    client: Any = None,
    config: ObservabilityConfig | None = None,
    mode: ObservabilityMode | None = None,
    service_name: str | None = None,
    collector_endpoint: str | None = None,
    tracer_provider: Any = None,
    meter_provider: Any = None,
    logger_provider: Any = None,
    enabled: bool = True,
) -> None
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `str` | `None` | Explicit API key (highest priority) |
| `client` | `BudClient \| AsyncBudClient` | `None` | SDK client instance; its `api_key` and `base_url` are used as defaults |
| `config` | `ObservabilityConfig` | `None` | Pre-built configuration (skips env resolution) |
| `mode` | `ObservabilityMode` | `None` | Override observability mode |
| `service_name` | `str` | `None` | Override service name |
| `collector_endpoint` | `str` | `None` | Override collector endpoint |
| `tracer_provider` | `TracerProvider` | `None` | Attach an external TracerProvider |
| `meter_provider` | `MeterProvider` | `None` | Attach an external MeterProvider |
| `logger_provider` | `LoggerProvider` | `None` | Attach an external LoggerProvider |
| `enabled` | `bool` | `True` | Enable or disable observability |

### Configuration Precedence

The SDK resolves configuration in the following order (highest to lowest priority):

1. Explicit keyword arguments (`api_key`, `collector_endpoint`, etc.)
2. Values extracted from the `client` parameter
3. `BUD_API_KEY` / `BUD_BASE_URL` environment variables
4. Defaults

### Examples

#### Configure from a client

```python
from bud import BudClient
from bud.observability import configure

client = BudClient(api_key="bud_xxxx", base_url="https://api.bud.io")
configure(client=client, service_name="my-service")
```

#### Configure with explicit API key

```python
from bud.observability import configure

configure(api_key="bud_xxxx", collector_endpoint="https://api.bud.io")
```

#### Configure with a custom config object

```python
from bud.observability import configure
from bud.observability import ObservabilityConfig, ObservabilityMode

config = ObservabilityConfig(
    mode=ObservabilityMode.CREATE,
    service_name="my-pipeline",
    batch_max_queue_size=4096,
    metrics_export_interval_ms=30000,
)
configure(config=config, api_key="bud_xxxx")
```

#### Attach mode — bring your own providers

```python
from bud.observability import configure, ObservabilityMode

configure(
    mode=ObservabilityMode.ATTACH,
    tracer_provider=my_tracer_provider,
    meter_provider=my_meter_provider,
)
```

## ObservabilityConfig

A dataclass holding the full configuration for the observability module.

```python
from bud.observability import ObservabilityConfig
```

### Fields

#### Core

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mode` | `ObservabilityMode` | `AUTO` | Provider strategy |
| `api_key` | `str \| None` | `None` | API key for authentication |
| `collector_endpoint` | `str \| None` | `None` | OTel collector endpoint |
| `service_name` | `str` | `"bud-sdk-client"` | Service name for resource |
| `enabled` | `bool` | `True` | Enable or disable observability |

#### Resource Attributes

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `service_version` | `str \| None` | `None` | Service version string |
| `deployment_environment` | `str \| None` | `None` | Deployment environment name |
| `resource_attributes` | `dict[str, str]` | `{}` | Additional resource attributes |

#### Traces

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `traces_enabled` | `bool` | `True` | Enable trace export |
| `batch_max_queue_size` | `int` | `2048` | Max spans in queue |
| `batch_max_export_size` | `int` | `512` | Max spans per export batch |
| `batch_schedule_delay_ms` | `int` | `1000` | Export delay in milliseconds |
| `export_timeout_ms` | `int` | `5000` | Export timeout in milliseconds |

#### Metrics

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `metrics_enabled` | `bool` | `True` | Enable metrics export |
| `metrics_export_interval_ms` | `int` | `60000` | Metrics export interval in milliseconds |

#### Logs

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `logs_enabled` | `bool` | `True` | Enable log export |
| `log_level` | `str` | `"WARNING"` | Minimum log level |

#### Network

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `compression` | `str` | `"gzip"` | Compression algorithm |
| `tls_insecure` | `bool` | `False` | Skip TLS verification |

#### External Providers

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `tracer_provider` | `Any` | `None` | External TracerProvider for ATTACH mode |
| `meter_provider` | `Any` | `None` | External MeterProvider for ATTACH mode |
| `logger_provider` | `Any` | `None` | External LoggerProvider for ATTACH mode |

### Example

```python
from bud.observability import ObservabilityConfig, ObservabilityMode

config = ObservabilityConfig(
    mode=ObservabilityMode.CREATE,
    service_name="rag-pipeline",
    service_version="1.2.0",
    deployment_environment="production",
    batch_max_queue_size=4096,
    batch_schedule_delay_ms=2000,
    metrics_export_interval_ms=30000,
    compression="gzip",
)
```

## ObservabilityMode

An enum controlling how the observability module creates or reuses OpenTelemetry providers.

```python
from bud.observability import ObservabilityMode
```

| Mode | Value | Description |
|------|-------|-------------|
| `AUTO` | `"auto"` | Automatically detect the best strategy (default) |
| `CREATE` | `"create"` | Always create new providers |
| `ATTACH` | `"attach"` | Attach to externally managed providers passed via `tracer_provider` / `meter_provider` / `logger_provider` |
| `INTERNAL` | `"internal"` | Apply aggressive batch defaults for internal services |
| `DISABLED` | `"disabled"` | Disable all observability |

## Lifecycle Management

### flush()

Force-flush all pending telemetry data before shutdown.

```python
from bud.observability import flush

success = flush(timeout_millis=30000)  # Returns True if all providers flushed
```

### shutdown()

Flush pending telemetry and release all resources.

```python
from bud.observability import shutdown

shutdown()
```

### is_configured()

Check whether observability has been configured.

```python
from bud.observability import is_configured

if is_configured():
    print("Observability is active")
```

### Recommended Pattern

```python
from bud.observability import configure, shutdown

configure(client=client, service_name="my-service")
try:
    # ... application code ...
finally:
    shutdown()
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BUD_OTEL_MODE` | Observability mode (`auto`, `create`, `attach`, `internal`, `disabled`) | `auto` |
| `BUD_OTEL_ENABLED` | Enable or disable observability (`true`, `false`) | `true` |
| `BUD_OTEL_SERVICE_NAME` | Service name for OTel resource (falls back to `OTEL_SERVICE_NAME`) | `bud-sdk-client` |
| `BUD_API_KEY` | API key for authentication | - |
| `BUD_BASE_URL` | Collector endpoint / base URL | - |

## Next Steps

- [Auto-Instrumentation](auto-instrumentation.md) — One-call patching for chat completions and responses
- [@track Decorator](track-decorator.md) — Declarative function tracing
- [Advanced Observability](advanced.md) — Manual spans, metrics, and context propagation
