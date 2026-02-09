# Observability Module — Implementation Tasks

## Phase 1: Foundation (Steps 1-5)

### Task 1: Create `_attributes.py`
- **File:** `src/bud/observability/_attributes.py`
- **Description:** Define all bud.* attribute constants matching gateway's baggage.rs
- **Acceptance Criteria:**
  - All 8 baggage keys defined as constants
  - `BAGGAGE_KEYS` list for BaggageSpanProcessor
  - SDK-specific attribute constants (version, language)
  - Constants match `/services/budgateway/tensorzero-internal/src/baggage.rs` exactly

### Task 2: Create `_noop.py`
- **File:** `src/bud/observability/_noop.py`
- **Description:** No-op implementations for when OTel deps are not installed
- **Acceptance Criteria:**
  - `_NoOpTracer` with `start_span()` and `start_as_current_span()` returning no-ops
  - `_NoOpSpan` with all Span interface methods as no-ops
  - `_NoOpMeter` with `create_counter()` etc. returning no-op instruments
  - `_check_otel_available()` function that tests importability
  - All methods are completely safe (no exceptions)

### Task 3: Create `_config.py`
- **File:** `src/bud/observability/_config.py`
- **Description:** ObservabilityConfig dataclass and ObservabilityMode enum
- **Acceptance Criteria:**
  - `ObservabilityMode` enum with AUTO, CREATE, ATTACH, INTERNAL, DISABLED
  - `ObservabilityConfig` dataclass with all fields documented
  - Environment variable resolution via `_resolve_from_env()` classmethod
  - Sensible defaults for all fields
  - Validation (e.g., endpoint must be a valid URL)

### Task 4: Create `_baggage.py`
- **File:** `src/bud/observability/_baggage.py`
- **Description:** BaggageSpanProcessor extracted from budprompt
- **Acceptance Criteria:**
  - `BaggageSpanProcessor(SpanProcessor)` class
  - `on_start()` copies BAGGAGE_KEYS from context to span attributes
  - Uses `_attributes.BAGGAGE_KEYS` (not hardcoded keys)
  - Identical behavior to budprompt's `shared/baggage_processor.py`
  - Unit test confirming correct key copying

### Task 5: Create `_propagation.py`
- **File:** `src/bud/observability/_propagation.py`
- **Description:** W3C propagator setup and context helpers
- **Acceptance Criteria:**
  - `setup_propagator()` sets CompositePropagator (TraceContext + Baggage)
  - `extract_from_request(request)` handles FastAPI Request, dict, httpx.Request
  - `inject_into_headers(headers)` injects current context
  - `extract_context(carrier)` thin wrapper around `propagate.extract()`

---

## Phase 2: Exporters and Providers (Steps 6-9)

### Task 6: Create `_exporter.py`
- **File:** `src/bud/observability/_exporter.py`
- **Description:** Authenticated OTLP HTTP exporters for traces, metrics, logs
- **Acceptance Criteria:**
  - `create_trace_exporter(config)` returns OTLPSpanExporter with auth headers
  - `create_metric_exporter(config)` returns OTLPMetricExporter with auth headers
  - `create_log_exporter(config)` returns OTLPLogExporter with auth headers
  - `_build_headers(config)` adds `Authorization: Bearer <key>` and `X-Bud-SDK-Version`
  - Compression configurable (gzip default)
  - Unit test confirming headers are set correctly

### Task 7: Create `_metrics.py`
- **File:** `src/bud/observability/_metrics.py`
- **Description:** Pre-defined meters and metric instruments
- **Acceptance Criteria:**
  - `setup_meters(meter_provider)` creates standard instruments
  - Counter: `bud.requests` (total inference requests)
  - Counter: `bud.tokens` (total tokens consumed)
  - Histogram: `bud.request.duration` (request duration in ms)
  - UpDownCounter: `bud.requests.active` (currently active requests)
  - All instruments use proper units and descriptions

### Task 8: Create `_logging.py`
- **File:** `src/bud/observability/_logging.py`
- **Description:** Python logging to OTel LoggerProvider bridge
- **Acceptance Criteria:**
  - `setup_log_provider(config)` creates LoggerProvider + BatchLogRecordProcessor
  - `setup_log_bridge(logger_provider, min_level)` attaches LoggingHandler to root logger
  - Configurable minimum log level (default WARNING)
  - Python log records become OTel log records with trace correlation

### Task 9: Create `_provider.py`
- **File:** `src/bud/observability/_provider.py`
- **Description:** Core provider strategy for all modes
- **Acceptance Criteria:**
  - `create_providers(config)` implements CREATE mode:
    - Creates Resource, TracerProvider, MeterProvider, LoggerProvider
    - Adds BaggageSpanProcessor first
    - Adds BatchSpanProcessor with authenticated exporter
    - Sets global providers and propagator
  - `attach_to_providers(config)` implements ATTACH mode:
    - Detects existing SDK TracerProvider
    - Adds processors without replacing provider
    - Falls back to CREATE if provider is proxy/noop
    - Does NOT override global propagator
  - `detect_mode(config)` implements AUTO detection
  - Returns `ProviderBundle` dataclass with all three providers

---

## Phase 3: Integration Layer (Steps 10-14)

### Task 10: Create `_instrumentors.py`
- **File:** `src/bud/observability/_instrumentors.py`
- **Description:** Auto-instrumentation registry with double-instrumentation guard
- **Acceptance Criteria:**
  - `InstrumentorRegistry.register_all(names, provider)` enables requested instrumentors
  - Supports: httpx, requests, fastapi, pydantic_ai
  - Each instrumentor checks `is_instrumented_by_opentelemetry` before calling
  - Missing dependency → debug log, skip (not error)
  - Failed instrumentation → warning log, continue
  - Returns list of actually enabled instrumentors

### Task 11: Create `_stream_wrapper.py`
- **File:** `src/bud/observability/_stream_wrapper.py`
- **Description:** Span wrapper for streaming inference responses
- **Acceptance Criteria:**
  - `TracedStream(inner, span, token)` wraps any iterator/async iterator
  - Records `bud.inference.ttft_ms` on first chunk
  - Records `bud.inference.chunks` on completion
  - Sets span status ERROR on exception
  - Properly ends span and detaches context in finally block
  - Supports both sync `__iter__` and async `__aiter__`

### Task 12: Create `_state.py`
- **File:** `src/bud/observability/_state.py`
- **Description:** Thread-safe singleton managing all provider lifecycle
- **Acceptance Criteria:**
  - `_ObservabilityState` class with `threading.Lock`
  - `configure(config)` — idempotent (second call warns, no-ops)
  - `shutdown()` — flushes and shuts down all owned providers
  - `get_tracer(name)` — returns tracer from provider (or no-op)
  - `get_meter(name)` — returns meter from provider (or no-op)
  - `is_configured` property
  - Module-level `_state = _ObservabilityState()` singleton

### Task 13: Create `__init__.py`
- **File:** `src/bud/observability/__init__.py`
- **Description:** Public API surface with lazy imports
- **Acceptance Criteria:**
  - `configure()` — main entry point with all overloads
  - `shutdown()`, `is_configured()`, `get_tracer()`, `get_meter()`
  - `extract_context()`, `inject_context()`, `extract_from_request()`
  - Lazy imports: only import OTel when `configure()` is called
  - `_check_otel_available()` guard logs warning and returns if deps missing
  - Entire `configure()` body wrapped in try/except (never crashes)
  - `__all__` exports all public names
  - TYPE_CHECKING block for static analysis

### Task 14: Update `pyproject.toml`
- **File:** `/home/budadmin/varunsr/BudAIFoundry-SDK/pyproject.toml`
- **Description:** Add instrumentor dependency extras
- **Acceptance Criteria:**
  - `observability-httpx` extra with httpx instrumentor
  - `observability-fastapi` extra with FastAPI instrumentor
  - `observability-requests` extra with requests instrumentor
  - `observability-internal` meta-extra for BudRuntime services
  - All extras include base `observability` extra as dependency

---

## Phase 4: Testing (Step 15)

### Task 15: Write tests
- **Files:** `tests/test_observability/`
- **Description:** Unit and integration tests
- **Acceptance Criteria:**
  - `test_config.py` — Config from args, env vars, defaults
  - `test_baggage.py` — BaggageSpanProcessor key copying
  - `test_exporter.py` — Auth headers on OTLP exporters
  - `test_provider.py` — CREATE, ATTACH, AUTO mode behavior
  - `test_noop.py` — No-op safety when OTel missing
  - `test_instrumentors.py` — Registry with missing/present deps
  - `test_metrics.py` — Pre-defined instruments creation
  - `test_logging.py` — Python log → OTel log bridge
  - `test_e2e.py` — Full configure → span → export cycle with InMemorySpanExporter
  - `test_attach.py` — ATTACH mode adds to existing provider
  - All tests pass with `pytest tests/test_observability/ -v`
