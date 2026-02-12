# Advanced Observability

Manual span creation, custom metrics, context propagation, and framework instrumentation.

> **Examples**: See [rag_pipeline.py](../../examples/observability/rag_pipeline.py) and [fastapi_instrumentation.py](../../examples/observability/fastapi_instrumentation.py) for working code examples.

## Manual Span Creation

### get_tracer()

Returns an OTel Tracer for manual span creation. Returns a no-op tracer if observability is not configured.

```python
from bud.observability import get_tracer

tracer = get_tracer("my-module")

with tracer.start_as_current_span("process-document") as span:
    span.set_attribute("document.id", doc_id)
    span.set_attribute("document.length", len(text))
    result = process(text)
    span.set_attribute("result.status", "success")
```

### create_traced_span()

Creates a span and attaches it to the current context. Useful when you need to manage the span lifecycle manually (e.g., across streaming boundaries).

```python
from bud.observability import create_traced_span

span, token = create_traced_span(
    "my-operation",
    tracer=get_tracer("my-module"),
    attributes={"key": "value"},
)
try:
    result = do_work()
    span.set_status(StatusCode.OK)
except Exception as exc:
    span.record_exception(exc)
    span.set_status(StatusCode.ERROR, str(exc))
    raise
finally:
    span.end()
    from opentelemetry import context
    context.detach(token)
```

**Signature:**

```python
create_traced_span(
    name: str,
    tracer: Any = None,
    attributes: dict[str, Any] | None = None,
) -> tuple[Span, ContextToken]
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | — | Span name |
| `tracer` | `Tracer \| None` | `None` | OTel tracer (defaults to `get_tracer()`) |
| `attributes` | `dict[str, Any] \| None` | `None` | Initial span attributes |

### get_current_span()

Returns the current active span from the OTel context.

```python
from bud.observability import get_current_span

span = get_current_span()
span.set_attribute("custom.key", "value")
```

### TracedStream

A wrapper for streaming iterators that manages span lifecycle. Used internally by `track_chat_completions()` and `track_responses()`.

```python
from bud.observability import TracedStream, create_traced_span

span, token = create_traced_span("my-stream")
stream = TracedStream(inner_iterator, span, token)

for item in stream:
    process(item)
# Span is automatically ended when iteration completes
```

## Custom Metrics

### get_meter()

Returns an OTel Meter for creating custom metrics. Returns a no-op meter if observability is not configured.

```python
from bud.observability import get_meter

meter = get_meter("my-module")

# Counter
request_counter = meter.create_counter(
    name="requests.total",
    description="Total number of requests",
    unit="1",
)
request_counter.add(1, {"endpoint": "/chat"})

# Histogram
latency_histogram = meter.create_histogram(
    name="request.duration",
    description="Request duration in seconds",
    unit="s",
)
latency_histogram.record(0.245, {"endpoint": "/chat"})
```

### RAG Pipeline Metrics Example

```python
from bud.observability import get_meter, get_tracer

meter = get_meter("rag")
tracer = get_tracer("rag")

docs_counter = meter.create_counter("rag.documents_processed")
retrieval_latency = meter.create_histogram("rag.retrieval_latency_ms")
pipeline_duration = meter.create_histogram("rag.pipeline_duration_ms")

def run_rag_pipeline(query):
    with tracer.start_as_current_span("rag-pipeline") as span:
        start = time.monotonic()

        # Retrieval stage
        with tracer.start_as_current_span("vector-retrieval"):
            t0 = time.monotonic()
            docs = vector_db.search(query, top_k=5)
            retrieval_latency.record((time.monotonic() - t0) * 1000)
            docs_counter.add(len(docs))

        # Generation stage
        with tracer.start_as_current_span("llm-generation"):
            response = client.chat.completions.create(...)

        pipeline_duration.record((time.monotonic() - start) * 1000)
        return response
```

## W3C Context Propagation

### extract_context()

Extracts W3C trace context from a dict of HTTP headers.

```python
from bud.observability import extract_context

# Incoming request headers
headers = {"traceparent": "00-abc123...-def456...-01"}
ctx = extract_context(headers)
```

### inject_context()

Injects the current trace context into outgoing HTTP headers.

```python
from bud.observability import inject_context

headers = {}
headers = inject_context(headers)
# headers now contains "traceparent" and optionally "tracestate"

response = httpx.get("https://api.example.com", headers=headers)
```

### extract_from_request()

Extracts trace context from a FastAPI `Request`, a dict, or an `httpx.Request` object.

```python
from bud.observability import extract_from_request

# In a FastAPI route
@app.post("/chat")
async def chat(request: Request):
    ctx = extract_from_request(request)
    # Use ctx to create child spans in the incoming trace
    with tracer.start_as_current_span("handle-chat", context=ctx):
        ...
```

### HTTP Propagation Example

```python
from bud.observability import extract_context, inject_context, get_tracer

tracer = get_tracer("my-service")

# Service A: inject context into outgoing request
with tracer.start_as_current_span("call-service-b"):
    headers = inject_context({})
    response = httpx.post("http://service-b/api", headers=headers)

# Service B: extract context from incoming request
incoming_headers = {"traceparent": request.headers["traceparent"]}
ctx = extract_context(incoming_headers)
with tracer.start_as_current_span("handle-request", context=ctx):
    process_request()
```

## Framework Instrumentation

### instrument_fastapi()

Instruments a FastAPI application for automatic distributed tracing.

```python
from fastapi import FastAPI
from bud.observability import configure, instrument_fastapi

app = FastAPI()
configure(client=client, service_name="my-api")
instrument_fastapi(app)
```

**Requires:** `pip install bud-sdk[observability-fastapi]`

**Signature:**

```python
instrument_fastapi(app: FastAPI, **kwargs) -> None
```

### instrument_httpx()

Instruments httpx clients for distributed tracing.

```python
from bud.observability import configure, instrument_httpx

configure(client=client, service_name="my-service")

# Instrument all httpx clients globally
instrument_httpx()

# Or instrument a specific client
import httpx
http_client = httpx.Client()
instrument_httpx(client=http_client)
```

**Requires:** `pip install bud-sdk[observability-httpx]`

**Signature:**

```python
instrument_httpx(client: httpx.Client | httpx.AsyncClient | None = None, **kwargs) -> None
```

### Complete FastAPI Example

```python
from fastapi import FastAPI, Request
from bud import BudClient
from bud.observability import (
    configure,
    instrument_fastapi,
    instrument_httpx,
    track_chat_completions,
    track,
    get_tracer,
    shutdown,
)

app = FastAPI()
client = BudClient(api_key="your-api-key")

# Set up observability
configure(client=client, service_name="my-api")
instrument_fastapi(app)
instrument_httpx()
track_chat_completions(client)

tracer = get_tracer("my-api")

@track(type="tool")
def validate_request(data: dict) -> dict:
    if not data.get("message"):
        raise ValueError("Message is required")
    return data

@app.post("/chat")
async def chat(request: Request):
    data = await request.json()

    with tracer.start_as_current_span("handle-chat"):
        validated = validate_request(data)
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": validated["message"]}],
        )
        return {"response": response.choices[0].message.content}

@app.on_event("shutdown")
async def app_shutdown():
    shutdown()
```

## Thread Safety

OTel context is thread-local. When spawning worker threads, propagate context explicitly:

```python
from concurrent.futures import ThreadPoolExecutor
from opentelemetry import context as otel_context
from bud.observability import get_tracer

tracer = get_tracer("my-module")

def _run_with_context(ctx, fn, *args):
    """Run a function in a worker thread with the parent's OTel context."""
    token = otel_context.attach(ctx)
    try:
        return fn(*args)
    finally:
        otel_context.detach(token)

with tracer.start_as_current_span("parallel-work"):
    ctx = otel_context.get_current()

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [
            pool.submit(_run_with_context, ctx, process_item, item)
            for item in items
        ]
        results = [f.result() for f in futures]
```

## BaggageSpanProcessor

A custom `SpanProcessor` that copies `bud.*` W3C Baggage entries to span attributes on span start. This enables per-project filtering through the baggage context.

```python
from bud.observability import BaggageSpanProcessor
```

The processor is automatically registered when using `configure()`. It copies any baggage keys prefixed with `bud.` to span attributes, allowing you to set project-level metadata that propagates across service boundaries.

```python
from opentelemetry import baggage, context

# Set baggage (propagates to downstream services)
ctx = baggage.set_baggage("bud.project_id", "my-project")
context.attach(ctx)

# All subsequent spans will have bud.project_id="my-project" as an attribute
```

## Best Practices

- **Namespace your tracers and meters** — Use descriptive names like `"my-service.retrieval"` to organize telemetry data
- **Call `flush()` and `shutdown()` at exit** — Ensures all pending telemetry is exported
- **Propagate context in threads** — Use `otel_context.get_current()` + `otel_context.attach()` for worker threads
- **Call `instrument_fastapi()` before serving** — Instrument the app after `configure()` and before `uvicorn.run()`
- **Use `instrument_httpx()` for cross-service tracing** — Automatically injects `traceparent` headers into outgoing requests
