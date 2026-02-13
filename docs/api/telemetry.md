# Telemetry Query API

Query OpenTelemetry span data collected by the BudAI platform.

> **Examples**: See [query_telemetry.py](../../examples/observability/query_telemetry.py) for working code examples.

> **Prerequisite**: The telemetry query API requires `app_url` to be configured on the client. This endpoint connects to the BudAI app service, not the gateway.

## Basic Usage

```python
from bud import BudClient

client = BudClient(
    api_key="your-api-key",
    app_url="https://app.bud.studio",
)

result = client.observability.query(
    prompt_id="my-prompt",
    from_date="2025-01-01T00:00:00Z",
)

for span in result.data:
    print(f"{span.span_name}: {span.duration}ns (trace: {span.trace_id})")

print(f"Page {result.page}/{result.total_pages} ({result.total_record} total)")
```

## Method Signature

```python
client.observability.query(
    prompt_id: str,
    from_date: str | datetime | None = None,
    *,
    version: str | None = None,
    to_date: str | datetime | None = None,
    trace_id: str | None = None,
    span_names: list[str] | None = None,
    depth: int = 0,
    select_attributes: list[str] | None = None,
    include_all_attributes: bool = False,
    include_resource_attributes: bool = False,
    include_events: bool = False,
    include_links: bool = False,
    span_filters: list[FilterCondition | dict] | None = None,
    resource_filters: list[FilterCondition | dict] | None = None,
    order_by: list[OrderBySpec | dict] | None = None,
    page: int = 1,
    limit: int = 10,
) -> TelemetryQueryResponse
```

## Parameters

### Required Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `prompt_id` | `str` | Prompt identifier to query spans for |

### Optional Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `from_date` | `str \| datetime` | `None` | Start of time range (ISO-8601 string or datetime) |
| `version` | `str` | `None` | Filter by prompt version |
| `to_date` | `str \| datetime` | `None` | End of time range (ISO-8601 string or datetime) |
| `trace_id` | `str` | `None` | Filter to a specific trace |
| `span_names` | `list[str]` | `None` | Filter by span names |
| `depth` | `int` | `0` | Child span depth (`0` = root only, `1` = root + children, `-1` = full tree) |
| `select_attributes` | `list[str]` | `None` | Specific attribute keys to include |
| `include_all_attributes` | `bool` | `False` | Include all span attributes |
| `include_resource_attributes` | `bool` | `False` | Include resource attributes |
| `include_events` | `bool` | `False` | Include span events |
| `include_links` | `bool` | `False` | Include span links |
| `span_filters` | `list[FilterCondition \| dict]` | `None` | Filters on span attributes |
| `resource_filters` | `list[FilterCondition \| dict]` | `None` | Filters on resource attributes |
| `order_by` | `list[OrderBySpec \| dict]` | `None` | Sort specifications |
| `page` | `int` | `1` | Page number (1-based) |
| `limit` | `int` | `10` | Results per page |

### Parameter Details

#### `from_date` / `to_date`

Accepts ISO-8601 strings or Python `datetime` objects. Naive datetimes (no timezone) are assumed UTC:

```python
# ISO-8601 string
result = client.observability.query(
    prompt_id="my-prompt",
    from_date="2025-01-01T00:00:00Z",
    to_date="2025-01-31T23:59:59Z",
)

# datetime objects
from datetime import datetime, timezone

result = client.observability.query(
    prompt_id="my-prompt",
    from_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
    to_date=datetime(2025, 1, 31, 23, 59, 59, tzinfo=timezone.utc),
)
```

#### `depth`

Controls how deep into the span tree to recurse:

| Value | Behavior |
|-------|----------|
| `0` | Root spans only (default) |
| `1` | Root spans + their immediate children |
| `-1` | Full trace tree (all descendants) |

```python
# Get full trace trees
result = client.observability.query(
    prompt_id="my-prompt",
    depth=-1,
)

for span in result.data:
    print(f"{span.span_name} ({span.child_count} children)")
    for child in span.children:
        print(f"  └── {child.span_name}")
```

#### `span_filters` / `resource_filters`

Filter conditions can be passed as `FilterCondition` objects or plain dicts:

```python
from bud.models.telemetry import FilterCondition, FilterOperator

# Using FilterCondition objects
result = client.observability.query(
    prompt_id="my-prompt",
    span_filters=[
        FilterCondition(field="status_code", op=FilterOperator.eq, value="ERROR"),
    ],
)

# Using plain dicts
result = client.observability.query(
    prompt_id="my-prompt",
    span_filters=[
        {"field": "status_code", "op": "eq", "value": "ERROR"},
    ],
)
```

#### `order_by`

Sort specifications can be passed as `OrderBySpec` objects or plain dicts:

```python
from bud.models.telemetry import OrderBySpec

# Using OrderBySpec objects
result = client.observability.query(
    prompt_id="my-prompt",
    order_by=[OrderBySpec(field="timestamp", direction="desc")],
)

# Using plain dicts
result = client.observability.query(
    prompt_id="my-prompt",
    order_by=[{"field": "duration", "direction": "desc"}],
)
```

## Filter Operators

```python
from bud.models.telemetry import FilterOperator
```

| Operator | Value | Description |
|----------|-------|-------------|
| `eq` | `"eq"` | Equal to |
| `neq` | `"neq"` | Not equal to |
| `gt` | `"gt"` | Greater than |
| `gte` | `"gte"` | Greater than or equal to |
| `lt` | `"lt"` | Less than |
| `lte` | `"lte"` | Less than or equal to |
| `in_` | `"in_"` | Value is in a list |
| `not_in` | `"not_in"` | Value is not in a list |
| `like` | `"like"` | Pattern match |
| `is_null` | `"is_null"` | Value is null |
| `is_not_null` | `"is_not_null"` | Value is not null |

## Response Objects

### TelemetryQueryResponse

```python
from bud.models.telemetry import TelemetryQueryResponse
```

| Field | Type | Description |
|-------|------|-------------|
| `object` | `str` | Always `"telemetry_query"` |
| `data` | `list[TelemetrySpanItem]` | List of span items |
| `page` | `int` | Current page number |
| `limit` | `int` | Results per page |
| `total_record` | `int` | Total number of matching records |
| `total_pages` | `int` | Total number of pages |
| `message` | `str \| None` | Optional status message |

### TelemetrySpanItem

```python
from bud.models.telemetry import TelemetrySpanItem
```

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | `str` | Span start timestamp |
| `trace_id` | `str` | Trace identifier |
| `span_id` | `str` | Span identifier |
| `parent_span_id` | `str` | Parent span ID (empty for root spans) |
| `trace_state` | `str` | W3C trace state |
| `span_name` | `str` | Span name |
| `span_kind` | `str` | Span kind (e.g., `"INTERNAL"`, `"SERVER"`) |
| `service_name` | `str` | Service name from resource |
| `scope_name` | `str` | Instrumentation scope name |
| `scope_version` | `str` | Instrumentation scope version |
| `duration` | `int` | Span duration in nanoseconds |
| `status_code` | `str` | Status code (`"OK"`, `"ERROR"`, `"UNSET"`) |
| `status_message` | `str` | Status message |
| `child_count` | `int` | Number of direct child spans |
| `children` | `list[TelemetrySpanItem]` | Child spans (populated when `depth > 0`) |
| `attributes` | `dict[str, str]` | Span attributes |
| `resource_attributes` | `dict[str, str] \| None` | Resource attributes (when `include_resource_attributes=True`) |
| `events` | `list[dict] \| None` | Span events (when `include_events=True`) |
| `links` | `list[dict] \| None` | Span links (when `include_links=True`) |

## Examples

### List Sessions

```python
result = client.observability.query(
    prompt_id="my-prompt",
    from_date="2025-01-01T00:00:00Z",
    limit=20,
)

for span in result.data:
    print(f"Trace: {span.trace_id}, Span: {span.span_name}, Duration: {span.duration}ns")
```

### Select Specific Attributes

```python
result = client.observability.query(
    prompt_id="my-prompt",
    select_attributes=["gen_ai.request.model", "gen_ai.usage.total_tokens"],
    include_all_attributes=True,
)

for span in result.data:
    model = span.attributes.get("gen_ai.request.model", "unknown")
    tokens = span.attributes.get("gen_ai.usage.total_tokens", "0")
    print(f"{span.span_name}: model={model}, tokens={tokens}")
```

### Full Trace Tree

```python
result = client.observability.query(
    prompt_id="my-prompt",
    depth=-1,
    include_all_attributes=True,
)

def print_tree(span, indent=0):
    prefix = "  " * indent + ("└── " if indent > 0 else "")
    print(f"{prefix}{span.span_name} ({span.duration}ns)")
    for child in span.children:
        print_tree(child, indent + 1)

for span in result.data:
    print_tree(span)
```

### Filter by Span Attributes

```python
from bud.models.telemetry import FilterCondition, FilterOperator

# Find error spans
result = client.observability.query(
    prompt_id="my-prompt",
    span_filters=[
        FilterCondition(field="status_code", op=FilterOperator.eq, value="ERROR"),
    ],
    include_all_attributes=True,
    include_events=True,
)

for span in result.data:
    print(f"ERROR: {span.span_name} - {span.status_message}")
```

### Filter by Resource Attributes

```python
result = client.observability.query(
    prompt_id="my-prompt",
    resource_filters=[
        FilterCondition(
            field="service.name",
            op=FilterOperator.eq,
            value="my-service",
        ),
    ],
    include_resource_attributes=True,
)
```

### Filter by Duration

```python
# Find slow spans (> 5 seconds = 5_000_000_000 nanoseconds)
result = client.observability.query(
    prompt_id="my-prompt",
    span_filters=[
        FilterCondition(field="duration", op=FilterOperator.gt, value="5000000000"),
    ],
)
```

### Pagination

```python
# Fetch page by page
page = 1
while True:
    result = client.observability.query(
        prompt_id="my-prompt",
        page=page,
        limit=50,
    )

    for span in result.data:
        process(span)

    if page >= result.total_pages:
        break
    page += 1
```

### Ordering

```python
from bud.models.telemetry import OrderBySpec

# Sort by duration descending (slowest first)
result = client.observability.query(
    prompt_id="my-prompt",
    order_by=[OrderBySpec(field="duration", direction="desc")],
    limit=10,
)

for span in result.data:
    duration_ms = span.duration / 1_000_000
    print(f"{span.span_name}: {duration_ms:.1f}ms")
```

### Combined Filters

```python
from bud.models.telemetry import FilterCondition, FilterOperator, OrderBySpec

result = client.observability.query(
    prompt_id="my-prompt",
    from_date="2025-01-01T00:00:00Z",
    to_date="2025-01-31T23:59:59Z",
    span_names=["chat", "responses"],
    depth=-1,
    span_filters=[
        FilterCondition(field="gen_ai.request.model", op=FilterOperator.eq, value="gpt-4"),
    ],
    resource_filters=[
        FilterCondition(field="service.name", op=FilterOperator.eq, value="my-service"),
    ],
    order_by=[OrderBySpec(field="timestamp", direction="desc")],
    include_all_attributes=True,
    include_events=True,
    include_links=True,
    page=1,
    limit=25,
)
```

### Using the IN Operator

```python
# Find spans for specific models
result = client.observability.query(
    prompt_id="my-prompt",
    span_filters=[
        FilterCondition(
            field="gen_ai.request.model",
            op=FilterOperator.in_,
            value=["gpt-4", "gpt-4.1", "gpt-3.5-turbo"],
        ),
    ],
)
```

## Async Usage

```python
import asyncio
from bud import AsyncBudClient

async def main():
    async with AsyncBudClient(
        api_key="your-api-key",
        app_url="https://app.bud.studio",
    ) as client:
        result = await client.observability.query(
            prompt_id="my-prompt",
            from_date="2025-01-01T00:00:00Z",
        )

        for span in result.data:
            print(f"{span.span_name}: {span.duration}ns")

asyncio.run(main())
```

## Error Handling

```python
from bud.exceptions import BudError, AuthenticationError, ValidationError

try:
    result = client.observability.query(
        prompt_id="my-prompt",
        from_date="2025-01-01T00:00:00Z",
    )
except AuthenticationError:
    print("Invalid API key")
except ValidationError as e:
    print(f"Invalid query parameters: {e}")
except BudError as e:
    print(f"API error: {e}")
```
