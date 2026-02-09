# Observability Module — Architecture & Design Plan

## Scope

**In scope:** Python SDK observability module (`src/bud/observability/`) covering traces, metrics, and logs.
**Out of scope:** OTel Collector auth infrastructure (planned separately). The SDK will pass the API key as an OTLP header; collector-side validation comes later.

---

## 1. Architecture Overview

### Design Principles
1. **Simplicity first** — 3-5 lines to initialize for external clients
2. **OTel-native** — Standard OTel APIs, W3C propagation, semantic conventions
3. **Non-invasive** — Detect and cooperate with existing TracerProviders (AUTO/ATTACH mode)
4. **API key passthrough** — SDK sends API key as `Authorization: Bearer <key>` header on OTLP exports
5. **Graceful degradation** — If OTel deps not installed (`pip install bud-sdk[observability]`), all calls are safe no-ops

### Signal Coverage (v1)
| Signal | OTel Component | Exporter |
|--------|---------------|----------|
| **Traces** | `TracerProvider` + `BatchSpanProcessor` | OTLP HTTP |
| **Metrics** | `MeterProvider` + `PeriodicExportingMetricReader` | OTLP HTTP |
| **Logs** | `LoggerProvider` + `BatchLogRecordProcessor` | OTLP HTTP |

### Mode System
| Mode | When | Behavior |
|------|------|----------|
| `AUTO` (default) | SDK detects environment | If existing SDK TracerProvider → ATTACH; else → CREATE |
| `CREATE` | Client has no OTel | SDK creates and owns all providers, sets globals |
| `ATTACH` | Client has existing OTel | SDK adds its processors/exporters to existing providers |
| `INTERNAL` | BudRuntime services | Full service mode: FastAPI instrumentor, PydanticAI, aggressive batching |
| `DISABLED` | Opt-out | All calls are no-ops |

---

## 2. Target Developer Experience

### External Client (minimal setup)
```python
from bud.observability import configure

configure(api_key="bud_client_xxxx", collector_endpoint="https://otel.bud.studio")
# Done. All httpx calls (including BudClient inference) are now traced.
```

### External Client (with existing OTel)
```python
from bud.observability import configure, ObservabilityMode

configure(
    api_key="bud_client_xxxx",
    mode=ObservabilityMode.ATTACH,  # Don't replace, add alongside
)
```

### Internal Service (replaces budprompt's OTelManager)
```python
from bud.observability import configure, ObservabilityMode

configure(
    mode=ObservabilityMode.INTERNAL,
    service_name="budprompt",
    collector_endpoint="http://otel-collector:4318",
    instrumentors=["httpx", "pydantic_ai", "fastapi"],
    enabled=not app_settings.otel_sdk_disabled,
)
```

---

## 3. Module File Structure

```
src/bud/observability/
├── __init__.py          # Public API surface (configure, shutdown, get_tracer, etc.)
├── _config.py           # ObservabilityConfig dataclass + ObservabilityMode enum
├── _state.py            # Thread-safe singleton managing provider lifecycle
├── _provider.py         # TracerProvider/MeterProvider/LoggerProvider strategy (CREATE/ATTACH/AUTO)
├── _exporter.py         # Authenticated OTLP exporters (traces, metrics, logs) with API key header
├── _baggage.py          # BaggageSpanProcessor (extracted from budprompt, single source of truth)
├── _attributes.py       # bud.* attribute constants (must match gateway's baggage.rs keys)
├── _propagation.py      # W3C propagator setup + context extract/inject helpers
├── _instrumentors.py    # Auto-instrumentation registry (httpx, requests, FastAPI, PydanticAI)
├── _metrics.py          # Pre-defined meters and instruments (request counters, token gauges, etc.)
├── _logging.py          # OTel LoggerProvider setup + Python logging bridge
├── _noop.py             # No-op implementations when OTel deps not installed
└── _stream_wrapper.py   # Span wrapper for streaming inference (manages span lifecycle over SSE)
```

**13 files total** (12 implementation + `__init__.py`).

---

## 4. Detailed Module Design

### 4.1 `_config.py` — Configuration

```python
class ObservabilityMode(str, Enum):
    AUTO = "auto"
    CREATE = "create"
    ATTACH = "attach"
    INTERNAL = "internal"
    DISABLED = "disabled"

@dataclass
class ObservabilityConfig:
    # Core
    mode: ObservabilityMode = ObservabilityMode.AUTO
    api_key: str | None = None
    collector_endpoint: str = "https://otel.bud.studio:4318"
    service_name: str = "bud-sdk-client"
    enabled: bool = True

    # Resource attributes
    service_version: str | None = None
    deployment_environment: str | None = None
    resource_attributes: dict[str, str] = field(default_factory=dict)

    # Traces - BatchSpanProcessor tuning
    traces_enabled: bool = True
    batch_max_queue_size: int = 2048
    batch_max_export_size: int = 512
    batch_schedule_delay_ms: int = 5000
    export_timeout_ms: int = 30000

    # Metrics - PeriodicExportingMetricReader tuning
    metrics_enabled: bool = True
    metrics_export_interval_ms: int = 60000  # 1 minute

    # Logs
    logs_enabled: bool = True
    log_level: str = "WARNING"  # Min level to export

    # Network
    compression: str = "gzip"  # gzip | none
    tls_insecure: bool = False

    # Auto-instrumentation
    instrumentors: list[str] = field(default_factory=lambda: ["httpx"])

    # External providers (for ATTACH mode)
    tracer_provider: Any = None
    meter_provider: Any = None
    logger_provider: Any = None
```

**Environment variable resolution** (lower priority than constructor args):
- `BUD_OTEL_API_KEY`, `BUD_OTEL_ENDPOINT`, `BUD_OTEL_SERVICE_NAME`
- `BUD_OTEL_MODE`, `BUD_OTEL_ENABLED`
- Falls back to standard OTel env vars: `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME`

### 4.2 `_attributes.py` — Semantic Constants

Must match budgateway's `baggage.rs` keys exactly:

```python
# W3C Baggage keys (set by gateway auth middleware)
PROJECT_ID = "bud.project_id"
PROMPT_ID = "bud.prompt_id"
PROMPT_VERSION_ID = "bud.prompt_version_id"
ENDPOINT_ID = "bud.endpoint_id"
MODEL_ID = "bud.model_id"
API_KEY_ID = "bud.api_key_id"
API_KEY_PROJECT_ID = "bud.api_key_project_id"
USER_ID = "bud.user_id"
AUTH_PROCESSED = "bud.auth_processed"

BAGGAGE_KEYS = [
    PROJECT_ID, PROMPT_ID, PROMPT_VERSION_ID, ENDPOINT_ID,
    MODEL_ID, API_KEY_ID, API_KEY_PROJECT_ID, USER_ID,
]

# SDK-specific attributes
SDK_VERSION = "bud.sdk.version"
SDK_LANGUAGE = "bud.sdk.language"
```

**Source of truth file:** `/home/budadmin/varunsr/bud-runtime/services/budgateway/tensorzero-internal/src/baggage.rs`

### 4.3 `_baggage.py` — BaggageSpanProcessor

Extracted from budprompt's `shared/baggage_processor.py` (identical logic, single source of truth):

```python
class BaggageSpanProcessor(SpanProcessor):
    """Copies bud.* W3C Baggage entries to span attributes on start."""
    def on_start(self, span, parent_context=None):
        ctx = parent_context or context.get_current()
        for key in BAGGAGE_KEYS:
            value = baggage.get_baggage(key, context=ctx)
            if value:
                span.set_attribute(key, value)
    # on_end, shutdown, force_flush are no-ops
```

### 4.4 `_exporter.py` — Authenticated OTLP Exporters

Wraps standard OTLP HTTP exporters, injecting `Authorization: Bearer <api_key>` header:

```python
def create_trace_exporter(config: ObservabilityConfig) -> SpanExporter:
    headers = _build_headers(config)
    return OTLPSpanExporter(
        endpoint=f"{config.collector_endpoint}/v1/traces",
        headers=headers,
        timeout=config.export_timeout_ms // 1000,
        compression=Compression.Gzip if config.compression == "gzip" else Compression.NoCompression,
    )

def create_metric_exporter(config: ObservabilityConfig) -> MetricExporter:
    headers = _build_headers(config)
    return OTLPMetricExporter(
        endpoint=f"{config.collector_endpoint}/v1/metrics",
        headers=headers,
        ...
    )

def create_log_exporter(config: ObservabilityConfig) -> LogExporter:
    headers = _build_headers(config)
    return OTLPLogExporter(
        endpoint=f"{config.collector_endpoint}/v1/logs",
        headers=headers,
        ...
    )

def _build_headers(config: ObservabilityConfig) -> dict[str, str]:
    headers = {}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    headers["X-Bud-SDK-Version"] = __version__
    return headers
```

**Why HTTP not gRPC:** Firewall-friendly, no grpcio dependency (~20MB), already declared in pyproject.toml.

### 4.5 `_provider.py` — Provider Strategy

Core logic for CREATE/ATTACH/AUTO modes:

**CREATE mode:**
1. Build `Resource` with service_name + version + env + custom attrs
2. Create `TracerProvider(resource=resource)`
3. Add `BaggageSpanProcessor` first
4. Create authenticated OTLP exporter → wrap in `BatchSpanProcessor` → add to provider
5. Create `MeterProvider` with `PeriodicExportingMetricReader` + authenticated metric exporter
6. Create `LoggerProvider` with `BatchLogRecordProcessor` + authenticated log exporter
7. Set global providers via `trace.set_tracer_provider()`, `metrics.set_meter_provider()`, `_logs.set_logger_provider()`
8. Setup W3C propagator (TraceContext + Baggage)
9. Run requested auto-instrumentors

**ATTACH mode:**
1. Get existing provider: `trace.get_tracer_provider()`
2. If it's an SDK `TracerProvider` (has `add_span_processor`):
   - Add `BaggageSpanProcessor`
   - Add `BatchSpanProcessor(authenticated_exporter)`
3. If it's a proxy/noop provider → fall back to CREATE
4. Same for MeterProvider and LoggerProvider if provided
5. Do NOT call `set_global_textmap()` (preserve client's propagator)

**AUTO mode detection:**
```python
from opentelemetry.sdk.trace import TracerProvider as SdkTracerProvider
provider = trace.get_tracer_provider()
has_existing = isinstance(provider, SdkTracerProvider)
# has_existing → ATTACH, else → CREATE
```

**INTERNAL mode:**
Same as CREATE but:
- No API key auth header (internal network)
- Service name from config (e.g., "budprompt")
- Collector endpoint internal (e.g., `http://otel-collector:4318`)
- Aggressive batch: 2s delay, 4096 queue, no compression
- Enables FastAPI + PydanticAI instrumentors

### 4.6 `_instrumentors.py` — Auto-Instrumentation Registry

```python
class InstrumentorRegistry:
    @classmethod
    def register_all(cls, names: list[str], tracer_provider) -> list[str]:
        enabled = []
        for name in names:
            try:
                handler = cls._REGISTRY.get(name)
                if handler:
                    handler(tracer_provider)
                    enabled.append(name)
            except ImportError:
                logger.debug(f"Instrumentor '{name}' skipped: dependency not installed")
            except Exception as e:
                logger.warning(f"Instrumentor '{name}' failed: {e}")
        return enabled

    _REGISTRY = {
        "httpx": _instrument_httpx,
        "requests": _instrument_requests,
        "fastapi": _instrument_fastapi,
        "pydantic_ai": _instrument_pydantic_ai,
    }
```

**Double-instrumentation guard:** Each instrumentor checks `is_instrumented_by_opentelemetry` before calling `.instrument()`.

### 4.7 `_metrics.py` — Pre-defined Instruments

Standard metrics the SDK creates automatically:

```python
def setup_meters(meter_provider) -> dict:
    meter = meter_provider.get_meter("bud.observability")
    return {
        "request_counter": meter.create_counter(
            "bud.requests", unit="1", description="Total inference requests"
        ),
        "token_counter": meter.create_counter(
            "bud.tokens", unit="1", description="Total tokens consumed"
        ),
        "request_duration": meter.create_histogram(
            "bud.request.duration", unit="ms", description="Request duration"
        ),
        "active_requests": meter.create_up_down_counter(
            "bud.requests.active", unit="1", description="Currently active requests"
        ),
    }
```

These are exposed via `get_meter()` for both SDK internal use and user custom metrics.

### 4.8 `_logging.py` — OTel Log Bridge

Bridges Python's `logging` module to OTel's LoggerProvider:

```python
def setup_log_bridge(logger_provider, min_level: str = "WARNING"):
    """Attach OTel log handler to Python root logger."""
    from opentelemetry._logs import set_logger_provider
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

    handler = LoggingHandler(
        level=getattr(logging, min_level),
        logger_provider=logger_provider,
    )
    logging.getLogger().addHandler(handler)
```

This means any `logging.warning("...")` call in the client's app automatically becomes an OTel log record exported to the collector.

### 4.9 `_propagation.py` — Context Helpers

```python
def setup_propagator():
    set_global_textmap(CompositePropagator([
        TraceContextTextMapPropagator(),
        W3CBaggagePropagator(),
    ]))

def extract_from_request(request) -> Context:
    """Extract trace context from FastAPI Request, dict carrier, or httpx.Request."""
    ...

def inject_into_headers(headers: dict) -> dict:
    """Inject current trace context into outgoing headers."""
    ...
```

### 4.10 `_state.py` — Thread-Safe Singleton

```python
class _ObservabilityState:
    def __init__(self):
        self._config = None
        self._tracer_provider = None
        self._meter_provider = None
        self._logger_provider = None
        self._owned_providers = False  # Did we create providers?
        self._is_configured = False
        self._lock = threading.Lock()

    def configure(self, config: ObservabilityConfig) -> None:
        with self._lock:
            if self._is_configured:
                logger.warning("Already configured, skipping")
                return
            # ... setup logic from _provider.py ...

    def shutdown(self) -> None:
        with self._lock:
            # flush + shutdown all owned providers

    def get_tracer(self, name: str) -> Tracer: ...
    def get_meter(self, name: str) -> Meter: ...

_state = _ObservabilityState()
```

### 4.11 `_noop.py` — Graceful Degradation

When OTel deps are not installed:

```python
def _check_otel_available() -> bool:
    try:
        import opentelemetry.sdk.trace
        return True
    except ImportError:
        return False

class _NoOpTracer:
    def start_span(self, name, **kw): return _NoOpSpan()
    def start_as_current_span(self, name, **kw): return contextlib.nullcontext(_NoOpSpan())
```

### 4.12 `_stream_wrapper.py` — Streaming Span Lifecycle

Wraps streaming inference responses to manage span lifecycle:

```python
class TracedStream(Generic[T]):
    """Wraps Stream[T] to track span across SSE streaming."""
    def __init__(self, inner, span, context_token):
        ...
    def __iter__(self):
        try:
            for chunk in self._inner:
                if self._first_chunk_time is None:
                    self._span.set_attribute("bud.inference.ttft_ms", ...)
                self._chunk_count += 1
                yield chunk
        except Exception as e:
            self._span.set_status(StatusCode.ERROR, str(e))
            raise
        finally:
            self._span.set_attribute("bud.inference.chunks", self._chunk_count)
            self._span.end()
            context.detach(self._context_token)
```

### 4.13 `__init__.py` — Public API

All public functions use lazy imports with `_check_otel_available()` guard:

```python
def configure(
    api_key: str | None = None,
    *,
    config: ObservabilityConfig | None = None,
    mode: ObservabilityMode | None = None,
    service_name: str | None = None,
    collector_endpoint: str | None = None,
    tracer_provider: Any = None,
    meter_provider: Any = None,
    logger_provider: Any = None,
    instrumentors: list[str] | None = None,
    enabled: bool = True,
) -> None: ...

def shutdown() -> None: ...
def is_configured() -> bool: ...
def get_tracer(name: str = "bud") -> Tracer | _NoOpTracer: ...
def get_meter(name: str = "bud") -> Meter | _NoOpMeter: ...
def extract_context(carrier: dict) -> Context: ...
def inject_context(carrier: dict) -> None: ...
def extract_from_request(request: Any) -> Context: ...

# Re-exports
__all__ = [
    "configure", "shutdown", "is_configured",
    "get_tracer", "get_meter",
    "extract_context", "inject_context", "extract_from_request",
    "ObservabilityConfig", "ObservabilityMode",
    "BaggageSpanProcessor", "TracedStream",
]
```

---

## 5. Context Propagation Flow (End-to-End)

```
CLIENT APP (SDK configured)        BUDGATEWAY (Rust)              BUDPROMPT (Python)
    |                                   |                              |
    | configure(api_key="bud_xx")       |                              |
    | httpx auto-instrumented           |                              |
    |                                   |                              |
    | client.chat.completions.create()  |                              |
    | [SDK httpx instrumentor injects   |                              |
    |  traceparent + tracestate headers]|                              |
    |                                   |                              |
    | --- POST /v1/chat/completions --> |                              |
    |   Authorization: Bearer bud_xx    |                              |
    |   traceparent: 00-<trace>-<span>  |                              |
    |                                   |                              |
    |                                   | [Auth validates key]         |
    |                                   | [Sets W3C Baggage:           |
    |                                   |  bud.project_id, etc.]       |
    |                                   |                              |
    |                                   | --- POST /v1/responses ----> |
    |                                   |   traceparent (child span)   |
    |                                   |   baggage: bud.project_id=.. |
    |                                   |                              |
    |                                   |                              | [extract(carrier)]
    |                                   |                              | [BaggageSpanProcessor]
    |                                   |                              | [PydanticAI agent runs]
    |                                   |                              | [httpx → LLM with trace]
    |                                   |                              |
    |                                   | <---- response ------------- |
    | <---- response ---------------    |                              |
    |                                   |                              |
    | [Spans exported to collector      |                              |
    |  via OTLP HTTP + Bearer token]    |                              |
```

**Key:** The same `trace_id` flows through all three services. Each creates child spans. Baggage is set by gateway and propagated to budprompt where `BaggageSpanProcessor` copies it to span attributes.

---

## 6. Dependency Changes

### `pyproject.toml` additions:

```toml
[project.optional-dependencies]
observability = [
    "opentelemetry-api>=1.20.0",
    "opentelemetry-sdk>=1.20.0",
    "opentelemetry-exporter-otlp-proto-http>=1.20.0",
]
# Individual instrumentor extras (opt-in)
observability-httpx = [
    "bud-sdk[observability]",
    "opentelemetry-instrumentation-httpx>=0.44b0",
]
observability-fastapi = [
    "bud-sdk[observability]",
    "opentelemetry-instrumentation-fastapi>=0.44b0",
]
observability-requests = [
    "bud-sdk[observability]",
    "opentelemetry-instrumentation-requests>=0.44b0",
]
# Meta-extra for internal services
observability-internal = [
    "bud-sdk[observability,observability-httpx,observability-fastapi]",
]
```

---

## 7. Error Handling Strategy

| Scenario | Behavior |
|----------|----------|
| OTel deps not installed | `configure()` logs warning, all calls become no-ops |
| Collector unreachable | Spans queue up to `max_queue_size`, then silently dropped. App never blocks. |
| API key invalid | OTLP export returns non-200. Spans dropped after retries. Warning logged once. |
| `configure()` called twice | Second call is ignored with warning |
| `configure()` throws | Exception caught, warning logged, tracing disabled |
| Memory pressure | `max_queue_size` caps in-memory buffer (default 2048 spans) |
| Double instrumentation | Each instrumentor checks `is_instrumented_by_opentelemetry` first |

**Core invariant:** Observability must NEVER crash the application or impact request latency.

---

## 8. Implementation Sequence

| Step | File | Description | Dependencies |
|------|------|-------------|--------------|
| 1 | `_attributes.py` | Baggage key constants | None |
| 2 | `_noop.py` | No-op tracer/meter/span | None |
| 3 | `_config.py` | Config dataclass + mode enum | Step 1 |
| 4 | `_baggage.py` | BaggageSpanProcessor | Step 1 |
| 5 | `_propagation.py` | W3C propagator setup | None |
| 6 | `_exporter.py` | Authenticated OTLP exporters | Step 3 |
| 7 | `_metrics.py` | Pre-defined meters/instruments | Step 3 |
| 8 | `_logging.py` | Python logging → OTel bridge | Step 3 |
| 9 | `_provider.py` | Provider strategy (CREATE/ATTACH) | Steps 4-8 |
| 10 | `_instrumentors.py` | Auto-instrumentation registry | Step 9 |
| 11 | `_stream_wrapper.py` | Streaming span wrapper | Step 9 |
| 12 | `_state.py` | Thread-safe singleton | Steps 9-10 |
| 13 | `__init__.py` | Public API surface | Step 12 |
| 14 | `pyproject.toml` | Dependency extras | None |
| 15 | Tests | Unit + integration tests | Step 13 |

---

## 9. Critical Files Referenced

### SDK (create/modify)
- `/home/budadmin/varunsr/BudAIFoundry-SDK/src/bud/observability/` — all 13 files above
- `/home/budadmin/varunsr/BudAIFoundry-SDK/pyproject.toml` — add dependency extras

### Existing code to reuse (read-only reference)
- `/home/budadmin/varunsr/bud-runtime/services/budprompt/budprompt/shared/baggage_processor.py` — Extract into SDK's `_baggage.py`
- `/home/budadmin/varunsr/bud-runtime/services/budprompt/budprompt/shared/otel.py` — Reference for OTelManager patterns
- `/home/budadmin/varunsr/bud-runtime/services/budgateway/tensorzero-internal/src/baggage.rs` — Source of truth for baggage key names

---

## 10. Verification Plan

### Unit Tests
- `test_config.py`: Config resolution from args, env vars, defaults
- `test_baggage.py`: BaggageSpanProcessor copies keys correctly
- `test_exporter.py`: Auth headers injected into OTLP exporters
- `test_provider.py`: CREATE/ATTACH/AUTO mode detection and behavior
- `test_noop.py`: No-op implementations don't throw
- `test_instrumentors.py`: Registry handles missing deps gracefully
- `test_metrics.py`: Pre-defined instruments created correctly
- `test_logging.py`: Python log records become OTel log records

### Integration Tests
- `test_e2e_traces.py`: Full configure → create span → export cycle (with mock collector)
- `test_e2e_attach.py`: ATTACH mode adds processor to existing provider without breaking it
- `test_e2e_propagation.py`: Trace context propagates through httpx calls
- `test_e2e_noop.py`: Everything works when OTel deps not installed

### Manual Verification
```bash
# Install with observability
pip install -e ".[observability,observability-httpx]"

# Run example script that calls BudClient + checks traces export
python examples/observability_example.py

# Verify no-op when deps missing
pip install -e .  # without [observability]
python -c "from bud.observability import configure; configure(api_key='test')"
# Should log warning, not crash
```
