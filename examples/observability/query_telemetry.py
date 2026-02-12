"""Example: Query telemetry data from the BudAI app service.

Demonstrates all telemetry query capabilities through 17 scenarios:
  - Session listing with depth control
  - Attribute selection and projection
  - Span and resource attribute filtering
  - Pagination and ordering

Requires:
  - BUD_API_KEY (or pass api_key to BudClient)
  - BUD_APP_URL (or pass app_url to BudClient)
"""

from bud import BudClient

# --- Client setup (Project A) ---
# API key determines which project the queries target.
client = BudClient(
    api_key="<api key>",
    app_url="https://app.dev.bud.studio",
)

PROMPT = "test-tool-name"
FROM = "2026-02-05"

# ─────────────────────────────────────────────────────────────────────────────
# 1. Session list (default, depth=0)
# ─────────────────────────────────────────────────────────────────────────────
print("\n--- 1. Session list (default, depth=0) ---")

result = client.observability.query(
    prompt_id=PROMPT,
    from_date=FROM,
)
print(f"Total: {result.total_record}")
for span in result.data:
    print(
        f"  [{span.span_name}] {span.trace_id} duration={span.duration}ns "
        f"children={len(span.children)} child_count={span.child_count}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. Session list with select_attributes
# ─────────────────────────────────────────────────────────────────────────────
print("\n--- 2. Session list with select_attributes ---")

result = client.observability.query(
    prompt_id=PROMPT,
    from_date=FROM,
    select_attributes=[
        "gateway_analytics.status_code",
        "gateway_analytics.total_duration_ms",
        "gen_ai.usage.input_tokens",
        "gen_ai.usage.output_tokens",
    ],
)
for span in result.data:
    print(f"  [{span.span_name}] {span.trace_id} attrs={span.attributes}")


# ─────────────────────────────────────────────────────────────────────────────
# 3. Sessions + direct children (depth=1)
# ─────────────────────────────────────────────────────────────────────────────
print("\n--- 3. Sessions + direct children (depth=1) ---")

result = client.observability.query(
    prompt_id=PROMPT,
    from_date=FROM,
    depth=1,
)
for span in result.data:
    child_names = [c.span_name for c in span.children]
    print(f"  [{span.span_name}] children={child_names}")
    for child in span.children:
        print(
            f"    [{child.span_name}] children={len(child.children)} child_count={child.child_count}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 4. Full trace tree (depth=-1) for a single trace
# ─────────────────────────────────────────────────────────────────────────────
print("\n--- 4. Full trace tree (depth=-1, single trace) ---")

# First get a trace_id from scenario 1
first_trace_id = result.data[0].trace_id if result.data else "unknown"
result = client.observability.query(
    prompt_id=PROMPT,
    from_date=FROM,
    trace_id=first_trace_id,
    depth=-1,
    include_all_attributes=True,
)
for span in result.data:
    print(
        f"  [{span.span_name}] {span.span_id} duration={span.duration}ns child_count={span.child_count}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 5. Span name filter (only HTTP spans)
# ─────────────────────────────────────────────────────────────────────────────
print("\n--- 5. Span name filter (POST /v1/responses only) ---")

result = client.observability.query(
    prompt_id=PROMPT,
    from_date=FROM,
    span_names=["POST /v1/responses"],
    depth=0,
)
print(f"Total: {result.total_record}")
for span in result.data:
    print(f"  [{span.span_name}] child_count={span.child_count} children={len(span.children)}")


# ─────────────────────────────────────────────────────────────────────────────
# 6. Multiple span names
# ─────────────────────────────────────────────────────────────────────────────
print("\n--- 6. Multiple span names ---")

result = client.observability.query(
    prompt_id=PROMPT,
    from_date=FROM,
    span_names=["chat gpt", "POST"],
    depth=0,
)
print(f"Total: {result.total_record}")
for span in result.data:
    print(f"  [{span.span_name}] {span.trace_id}")


# ─────────────────────────────────────────────────────────────────────────────
# 7. Span attribute filter (only error sessions)
# ─────────────────────────────────────────────────────────────────────────────
print("\n--- 7. Span attribute filter (errors only, status_code != 200) ---")

result = client.observability.query(
    prompt_id=PROMPT,
    from_date=FROM,
    span_filters=[
        {"field": "gateway_analytics.status_code", "op": "neq", "value": "200"},
    ],
    select_attributes=["gateway_analytics.status_code", "gateway_analytics.error_message"],
)
print(f"Error sessions: {result.total_record}")
for span in result.data:
    print(f"  [{span.span_name}] {span.trace_id} attrs={span.attributes}")


# ─────────────────────────────────────────────────────────────────────────────
# 8. Span attribute filter (only successful sessions)
# ─────────────────────────────────────────────────────────────────────────────
print("\n--- 8. Span attribute filter (success only, status_code=200) ---")

result = client.observability.query(
    prompt_id=PROMPT,
    from_date=FROM,
    span_filters=[
        {"field": "gateway_analytics.status_code", "op": "eq", "value": "200"},
    ],
)
print(f"Successful sessions: {result.total_record}")
for span in result.data:
    print(f"  [{span.span_name}] {span.trace_id}")


# ─────────────────────────────────────────────────────────────────────────────
# 9. Resource attribute filter (filter by service)
# ─────────────────────────────────────────────────────────────────────────────
print("\n--- 9. Resource attribute filter (service.name=budgateway) ---")

result = client.observability.query(
    prompt_id=PROMPT,
    from_date=FROM,
    resource_filters=[
        {"field": "service.name", "op": "eq", "value": "budgateway"},
    ],
)
print(f"Sessions from budgateway: {result.total_record}")
for span in result.data:
    print(f"  [{span.span_name}] {span.trace_id}")


# ─────────────────────────────────────────────────────────────────────────────
# 10. Duration filter (slow requests only)
# ─────────────────────────────────────────────────────────────────────────────
print("\n--- 10. Duration filter (total_duration_ms > 10000) ---")

# Using Project A prompt; adjust threshold to match your data
result = client.observability.query(
    prompt_id=PROMPT,
    from_date=FROM,
    span_filters=[
        {"field": "gateway_analytics.total_duration_ms", "op": "gt", "value": "10000"},
    ],
    select_attributes=["gateway_analytics.total_duration_ms"],
)
print(f"Slow sessions: {result.total_record}")
for span in result.data:
    print(f"  [{span.span_name}] {span.trace_id} attrs={span.attributes}")


# ─────────────────────────────────────────────────────────────────────────────
# 11. Combined filters + span_names + depth
# ─────────────────────────────────────────────────────────────────────────────
print("\n--- 11. Combined: span_names + depth=2 + resource_filters + events + links ---")

result = client.observability.query(
    prompt_id=PROMPT,
    from_date=FROM,
    span_names=["POST /v1/responses"],
    depth=2,
    resource_filters=[
        {"field": "service.name", "op": "eq", "value": "budgateway"},
    ],
    include_events=True,
    include_links=True,
)
print(f"Total: {result.total_record}")
for span in result.data:
    print(f"  [{span.span_name}] events={span.events} links={span.links}")
    for child in span.children:
        print(f"    [{child.span_name}] children={len(child.children)}")
        for grandchild in child.children:
            print(f"      [{grandchild.span_name}]")


# ─────────────────────────────────────────────────────────────────────────────
# 12. Pagination (page-based)
# ─────────────────────────────────────────────────────────────────────────────
print("\n--- 12. Pagination (limit=2) ---")

page1 = client.observability.query(
    prompt_id=PROMPT,
    from_date=FROM,
    page=1,
    limit=2,
)
print(f"Page {page1.page}/{page1.total_pages}: {len(page1.data)} of {page1.total_record}")

page2 = client.observability.query(
    prompt_id=PROMPT,
    from_date=FROM,
    page=2,
    limit=2,
)
print(f"Page {page2.page}/{page2.total_pages}: {len(page2.data)} of {page2.total_record}")


# ─────────────────────────────────────────────────────────────────────────────
# 13. Order by (ascending timestamp)
# ─────────────────────────────────────────────────────────────────────────────
print("\n--- 13. Order by timestamp ascending ---")

result = client.observability.query(
    prompt_id=PROMPT,
    from_date=FROM,
    order_by=[{"field": "timestamp", "direction": "asc"}],
    select_attributes=["gateway_analytics.total_duration_ms"],
)
for i, span in enumerate(result.data):
    print(f"  {i + 1}. [{span.span_name}] {span.timestamp} attrs={span.attributes}")


# ─────────────────────────────────────────────────────────────────────────────
# 14. Version filter
# ─────────────────────────────────────────────────────────────────────────────
print("\n--- 14. Version filter (version=1) ---")

result = client.observability.query(
    prompt_id=PROMPT,
    from_date=FROM,
    version="1",
)
print(f"Sessions with version=1: {result.total_record}")
for span in result.data:
    print(f"  [{span.span_name}] {span.trace_id}")


# ─────────────────────────────────────────────────────────────────────────────
# 15. IN filter operator
# ─────────────────────────────────────────────────────────────────────────────
print("\n--- 15. IN filter (status_code IN [200, 500]) ---")

result = client.observability.query(
    prompt_id=PROMPT,
    from_date=FROM,
    span_filters=[
        {"field": "gateway_analytics.status_code", "op": "in_", "value": ["200", "500"]},
    ],
    select_attributes=["gateway_analytics.status_code"],
)
print(f"Sessions matching IN filter: {result.total_record}")
for span in result.data:
    print(
        f"  [{span.span_name}] {span.trace_id} status={span.attributes.get('gateway_analytics.status_code')}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 16. include_resource_attributes only
# ─────────────────────────────────────────────────────────────────────────────
print("\n--- 16. include_resource_attributes only ---")

result = client.observability.query(
    prompt_id=PROMPT,
    from_date=FROM,
    include_resource_attributes=True,
    depth=0,
)
for span in result.data:
    print(f"  [{span.span_name}] resource_attributes={span.resource_attributes}")


# ─────────────────────────────────────────────────────────────────────────────
# 17. Time range with explicit to_date
# ─────────────────────────────────────────────────────────────────────────────
print("\n--- 17. Time range with explicit to_date (1-minute window) ---")

result = client.observability.query(
    prompt_id=PROMPT,
    from_date="2026-02-05T13:07:00+00:00",
    to_date="2026-02-05T13:08:00+00:00",
)
print(f"Sessions in window: {result.total_record}")
for span in result.data:
    print(f"  [{span.span_name}] {span.timestamp}")


# ─────────────────────────────────────────────────────────────────────────────
# Cleanup
# ─────────────────────────────────────────────────────────────────────────────
client.close()
print("\nDone.")
