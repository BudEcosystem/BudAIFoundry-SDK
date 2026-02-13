# @track Decorator

Declarative OpenTelemetry tracing for your own functions.

> **Examples**: See [track_non_streaming.py](../../examples/observability/track_non_streaming.py) and [track_streaming.py](../../examples/observability/track_streaming.py) for working code examples.

## Basic Usage

```python
from bud.observability import configure, track, shutdown

configure(api_key="your-api-key", service_name="my-service")

@track
def process_document(text):
    # ... your logic ...
    return {"summary": "...", "word_count": 42}

result = process_document("Hello, world!")
shutdown()
```

## Decorator Signature

The `@track` decorator can be used in three forms:

```python
@track                    # Bare — auto-detects function name
def my_func(): ...

@track()                  # Empty call — same as bare
def my_func(): ...

@track(name="custom-name", type="llm", capture_input=True)
def my_func(): ...        # With options
```

### Full Signature

```python
from bud.observability import track

@track(
    name: str | None = None,
    tracer_name: str = "bud",
    capture_input: bool = True,
    ignore_arguments: list[str] | None = None,
    capture_output: bool = True,
    generations_aggregator: Callable[[list[Any]], Any] | None = None,
    type: str | None = None,
    attributes: dict[str, Any] | None = None,
)
```

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str \| None` | `None` | Span name. Defaults to `fn.__qualname__` |
| `tracer_name` | `str` | `"bud"` | OTel tracer name |
| `capture_input` | `bool` | `True` | Record function arguments as span attributes |
| `ignore_arguments` | `list[str] \| None` | `None` | Argument names to exclude from capture |
| `capture_output` | `bool` | `True` | Record return value as span attributes |
| `generations_aggregator` | `Callable[[list[Any]], Any] \| None` | `None` | Custom aggregator for generator outputs |
| `type` | `str \| None` | `None` | Sets `bud.track.type` attribute (e.g., `"llm"`, `"tool"`, `"chain"`) |
| `attributes` | `dict[str, Any] \| None` | `None` | Static attributes added to every span invocation |

## Span Attributes

### Input Capture

When `capture_input=True`, function arguments are recorded as:

| Attribute Pattern | Description |
|-------------------|-------------|
| `bud.track.input.<param_name>` | `repr()` of each argument |

- `self` and `cls` are automatically skipped
- Arguments listed in `ignore_arguments` are excluded
- Values are truncated to 1000 characters

### Output Capture

When `capture_output=True`, the return value is recorded as:

| Return Type | Attribute |
|-------------|-----------|
| Non-dict | `bud.track.output` = `repr(result)` |
| Dict | `bud.track.output.<key>` = `repr(value)` for each key |

### Generator Output

For generator functions, additional attributes are recorded:

| Attribute | Description |
|-----------|-------------|
| `bud.track.yield_count` | Number of items yielded |
| `bud.track.generator_completed` | `true` if the generator was fully consumed |
| `bud.track.output` | Aggregated output (string-join for str items, list repr otherwise) |

### Static Attributes

When `attributes` is provided, all key-value pairs are set on every span:

```python
@track(attributes={"environment": "production", "version": "1.0"})
def my_func(): ...
# Span has: environment="production", version="1.0"
```

### Type Attribute

When `type` is provided, `bud.track.type` is set on the span:

```python
@track(type="llm")
def ask(question): ...
# Span has: bud.track.type="llm"
```

## Function Types

### Regular Functions

```python
@track
def classify(text):
    return {"label": "positive", "score": 0.95}

result = classify("Great product!")
# Span: "classify"
#   bud.track.input.text = "'Great product!'"
#   bud.track.output.label = "'positive'"
#   bud.track.output.score = '0.95'
```

### Async Functions

```python
@track
async def fetch_data(url):
    async with httpx.AsyncClient() as client:
        return (await client.get(url)).json()

data = await fetch_data("https://api.example.com/data")
# Span: "fetch_data" — same attributes as sync version
```

### Sync Generators

```python
@track
def stream_response(client, prompt):
    stream = client.chat.completions.create(
        model="gpt-4", messages=[{"role": "user", "content": prompt}], stream=True
    )
    for chunk in stream:
        text = chunk.choices[0].delta.content or ""
        yield text

for token in stream_response(client, "Count to 5"):
    print(token, end="")
# Span: "stream_response"
#   bud.track.yield_count = <number of chunks>
#   bud.track.generator_completed = true
#   bud.track.output = "'12345'" (string-joined)
```

### Async Generators

```python
@track
async def async_stream(client, prompt):
    stream = await client.chat.completions.create(
        model="gpt-4", messages=[{"role": "user", "content": prompt}], stream=True
    )
    async for chunk in stream:
        yield chunk.choices[0].delta.content or ""
```

## Examples

### Named span with type

```python
@track(name="sentiment-analysis", type="tool")
def analyze_sentiment(text):
    response = client.classifications.create(model="finbert", input=[text])
    return {"label": response.data[0][0].label, "score": response.data[0][0].score}
```

### Suppress output capture

```python
@track(capture_output=False)
def process_large_document(doc):
    # Return value is large; don't record it on the span
    return {"tokens": [...], "embeddings": [...]}
```

### Ignore sensitive arguments

```python
@track(ignore_arguments=["api_key", "client"])
def call_external_api(client, query, api_key):
    return client.get(query, headers={"Authorization": api_key})
# Span only records: bud.track.input.query
```

### Static attributes

```python
@track(attributes={"pipeline": "rag", "stage": "retrieval"})
def retrieve_documents(query, top_k=5):
    # ... vector search ...
    return results
```

### Pipeline chain (nested spans)

```python
@track(name="rag-pipeline", type="chain")
def run_pipeline(query):
    docs = retrieve(query)
    context = format_context(docs)
    return generate(context, query)

@track(name="retrieve", type="tool")
def retrieve(query):
    return vector_db.search(query)

@track(name="format-context", type="tool")
def format_context(docs):
    return "\n".join(d.text for d in docs)

@track(name="generate", type="llm")
def generate(context, query):
    return client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": f"Context: {context}"},
            {"role": "user", "content": query},
        ],
    )

result = run_pipeline("What is RAG?")
# Trace: rag-pipeline → retrieve → format-context → generate
```

### Custom generator aggregator

```python
def aggregate_chunks(items):
    """Custom aggregator that extracts text from chunk objects."""
    return "".join(chunk.text for chunk in items if hasattr(chunk, "text"))

@track(generations_aggregator=aggregate_chunks)
def stream_with_objects(prompt):
    for chunk in get_chunks(prompt):
        yield chunk
# bud.track.output = aggregated text from custom function
```

### Class methods

```python
class DocumentAnalyzer:
    @track(name="analyze-document", type="chain")
    def analyze(self, document):
        summary = self.summarize(document)
        entities = self.extract_entities(document)
        return {"summary": summary, "entities": entities}

    @track(type="tool")
    def summarize(self, text):
        return client.chat.completions.create(...)

    @track(type="tool")
    def extract_entities(self, text):
        return client.classifications.create(...)

# `self` is automatically skipped in input capture
```

### Error recording

```python
@track
def risky_operation(data):
    if not data:
        raise ValueError("Empty data")
    return process(data)

try:
    risky_operation(None)
except ValueError:
    pass
# Span has StatusCode.ERROR with exception recorded
```

### Partial consumption of generators

```python
@track
def infinite_stream():
    i = 0
    while True:
        yield f"item-{i}"
        i += 1

gen = infinite_stream()
for i, item in enumerate(gen):
    if i >= 5:
        break
# Span: bud.track.yield_count=6, bud.track.generator_completed=false
```

## No-Op Behavior

The `@track` decorator is safe to use before `configure()` is called. When observability is not configured, the decorator is a transparent no-op — the original function runs without any overhead:

```python
@track
def my_func():
    return 42

# Before configure(): my_func() runs directly, no span created
result = my_func()  # Returns 42 with zero overhead

# After configure(): spans are created normally
configure(client=client)
result = my_func()  # Returns 42 with a span
```

## Best Practices

- **Use `type=` to categorize spans** — Common values: `"llm"`, `"tool"`, `"chain"`, `"retrieval"`, `"embedding"`. This enables filtering in your observability backend
- **Set `capture_input=False` on pipeline functions** — Intermediate functions in a chain often receive large objects; skip capture to reduce span size
- **Use `ignore_arguments` for non-serializable objects** — Client instances, database connections, and similar objects should be excluded
- **Combine with auto-instrumentation** — Use `@track` on your functions and `track_chat_completions()` / `track_responses()` on the client to get full end-to-end traces
- **Call `configure()` early** — The decorator silently no-ops until observability is configured, so set up early to capture all spans
