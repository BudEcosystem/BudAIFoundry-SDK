# Observability Module — Technical Specification

## 1. Overview

The `bud.observability` module provides a unified, OTel-native observability layer for the BudAIFoundry SDK. It wraps OpenTelemetry to deliver distributed tracing, metrics, and structured logging with minimal configuration.

---

## 2. Requirements

### 2.1 Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Single `configure()` call initializes traces, metrics, and logs | Must |
| FR-2 | API key passed as Bearer token in OTLP export headers | Must |
| FR-3 | Auto-detect existing OTel setup and cooperate (ATTACH mode) | Must |
| FR-4 | BaggageSpanProcessor copies bud.* baggage to span attributes | Must |
| FR-5 | W3C TraceContext + Baggage propagation via CompositePropagator | Must |
| FR-6 | Auto-instrument httpx for outgoing HTTP trace context injection | Must |
| FR-7 | Graceful no-op when OTel deps not installed | Must |
| FR-8 | Auto-instrument FastAPI for incoming request spans | Should |
| FR-9 | Auto-instrument PydanticAI agents | Should |
| FR-10 | Pre-defined metrics (request count, token count, duration histogram) | Should |
| FR-11 | Python logging bridge to OTel LoggerProvider | Should |
| FR-12 | Streaming span wrapper (TracedStream) for SSE responses | Should |
| FR-13 | Environment variable configuration fallback | Should |
| FR-14 | Thread-safe singleton preventing double-configuration | Must |

### 2.2 Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-1 | Synchronous overhead per request | < 1ms |
| NFR-2 | Memory usage (span queue) | < 10MB default |
| NFR-3 | Application never crashes due to observability failure | Always |
| NFR-4 | Application never blocks due to collector being unreachable | Always |
| NFR-5 | Compatible with Python 3.10+ | Always |
| NFR-6 | Compatible with OTel Python SDK >= 1.20.0 | Always |
| NFR-7 | No hard dependency on OTel (optional extra) | Always |

---

## 3. Architecture

### 3.1 Component Diagram

```
┌─────────────────────────────────────────────────────┐
│                  __init__.py                          │
│  configure() | shutdown() | get_tracer() | get_meter()│
└───────────────────────┬─────────────────────────────┘
                        │
                   ┌────▼────┐
                   │ _state  │ (singleton, thread-safe)
                   └────┬────┘
                        │
          ┌─────────────┼─────────────┐
          │             │             │
     ┌────▼────┐  ┌────▼────┐  ┌────▼────┐
     │_provider│  │_metrics │  │_logging │
     │ (trace) │  │ (meter) │  │ (logs)  │
     └────┬────┘  └────┬────┘  └────┬────┘
          │             │             │
     ┌────▼─────────────▼─────────────▼────┐
     │            _exporter.py              │
     │  (Authenticated OTLP HTTP exporters) │
     │  Authorization: Bearer <api_key>     │
     └────────────────┬────────────────────┘
                      │ OTLP HTTP
                      ▼
              OTel Collector
```

### 3.2 Provider Mode Decision Tree

```
configure() called
    │
    ├─ mode=DISABLED → return (no-op)
    │
    ├─ mode=CREATE → create new providers, set globals
    │
    ├─ mode=ATTACH → add processors to existing providers
    │
    ├─ mode=INTERNAL → CREATE + service instrumentors + aggressive batching
    │
    └─ mode=AUTO (default)
         │
         ├─ existing SDK TracerProvider? → ATTACH
         └─ no existing provider? → CREATE
```

### 3.3 Exporter Authentication

The SDK passes the API key as an HTTP header on every OTLP export request:

```
POST /v1/traces HTTP/1.1
Host: otel.bud.studio:4318
Authorization: Bearer bud_client_xxxx
Content-Type: application/x-protobuf
Content-Encoding: gzip
X-Bud-SDK-Version: 0.1.0
```

This is identical to how Honeycomb (`x-honeycomb-team`) and Grafana Cloud (`Authorization: Basic`) handle API key auth for OTLP ingestion.

### 3.4 Baggage Propagation

The gateway sets W3C Baggage after API key auth. The SDK's `BaggageSpanProcessor` copies these to span attributes on every span start, enabling per-project filtering in ClickHouse.

Baggage flow: `Client → (no baggage) → Gateway (sets baggage) → BudPrompt (reads baggage) → LLM`
Span attributes: All spans in the trace get `bud.project_id`, `bud.endpoint_id`, etc.

---

## 4. API Reference

### 4.1 `configure(**kwargs) -> None`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `str \| None` | `None` | BudRuntime API key for OTLP auth |
| `config` | `ObservabilityConfig \| None` | `None` | Full config object (overrides all) |
| `mode` | `ObservabilityMode \| None` | `AUTO` | Provider strategy |
| `service_name` | `str \| None` | `"bud-sdk-client"` | OTel service.name |
| `collector_endpoint` | `str \| None` | `"https://otel.bud.studio:4318"` | OTLP HTTP endpoint |
| `tracer_provider` | `TracerProvider \| None` | `None` | External provider for ATTACH |
| `meter_provider` | `MeterProvider \| None` | `None` | External provider for ATTACH |
| `instrumentors` | `list[str] \| None` | `["httpx"]` | Auto-instrumentors to enable |
| `enabled` | `bool` | `True` | Master enable/disable |

### 4.2 `shutdown() -> None`
Flushes pending telemetry and releases resources. Call on application exit.

### 4.3 `get_tracer(name: str = "bud") -> Tracer`
Returns OTel Tracer for manual span creation. Returns no-op tracer if not configured.

### 4.4 `get_meter(name: str = "bud") -> Meter`
Returns OTel Meter for custom metrics. Returns no-op meter if not configured.

### 4.5 `extract_context(carrier: dict) -> Context`
Extract W3C trace context from a dict of HTTP headers.

### 4.6 `inject_context(carrier: dict) -> None`
Inject current trace context into outgoing HTTP headers.

---

## 5. Configuration Precedence

1. Explicit constructor arguments (highest)
2. `BUD_OTEL_*` environment variables
3. Standard `OTEL_*` environment variables
4. Defaults (lowest)

---

## 6. Exporter Settings

| Setting | External (CREATE/ATTACH) | Internal (INTERNAL) |
|---------|--------------------------|---------------------|
| Protocol | OTLP HTTP (protobuf) | OTLP HTTP (protobuf) |
| Endpoint | `https://otel.bud.studio:4318` | `http://otel-collector:4318` |
| Compression | gzip | none |
| Auth | Bearer token | none |
| Batch queue | 2048 spans | 4096 spans |
| Batch delay | 5000ms | 2000ms |
| Batch size | 512 spans | 1024 spans |
| Metrics interval | 60s | 30s |

---

## 7. Compatibility Matrix

| Component | Minimum Version |
|-----------|----------------|
| Python | 3.10 |
| opentelemetry-api | 1.20.0 |
| opentelemetry-sdk | 1.20.0 |
| opentelemetry-exporter-otlp-proto-http | 1.20.0 |
| httpx | 0.27.0 |
