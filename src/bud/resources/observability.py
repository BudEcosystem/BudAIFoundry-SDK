"""Observability resource for the BudAI SDK."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from bud.models.telemetry import (
    FilterCondition,
    OrderBySpec,
    TelemetryQueryResponse,
)
from bud.resources._base import AsyncResource, SyncResource


def _build_query_payload(
    prompt_id: str,
    from_date: datetime,
    *,
    version: str | None = None,
    to_date: datetime | None = None,
    trace_id: str | None = None,
    span_names: list[str] | None = None,
    depth: int = 0,
    select_attributes: list[str] | None = None,
    include_all_attributes: bool = False,
    include_resource_attributes: bool = False,
    include_events: bool = False,
    include_links: bool = False,
    span_filters: list[FilterCondition] | None = None,
    resource_filters: list[FilterCondition] | None = None,
    order_by: list[OrderBySpec] | None = None,
    page: int = 1,
    limit: int = 10,
) -> dict[str, Any]:
    """Build the JSON payload for a telemetry query request."""
    payload: dict[str, Any] = {
        "prompt_id": prompt_id,
        "from_date": from_date.isoformat(),
    }
    if version is not None:
        payload["version"] = version
    if to_date is not None:
        payload["to_date"] = to_date.isoformat()
    if trace_id is not None:
        payload["trace_id"] = trace_id
    if span_names is not None:
        payload["span_names"] = span_names
    if depth != 0:
        payload["depth"] = depth
    if select_attributes is not None:
        payload["select_attributes"] = select_attributes
    if include_all_attributes:
        payload["include_all_attributes"] = True
    if include_resource_attributes:
        payload["include_resource_attributes"] = True
    if include_events:
        payload["include_events"] = True
    if include_links:
        payload["include_links"] = True
    if span_filters is not None:
        payload["span_filters"] = [f.model_dump() for f in span_filters]
    if resource_filters is not None:
        payload["resource_filters"] = [f.model_dump() for f in resource_filters]
    if order_by is not None:
        payload["order_by"] = [o.model_dump() for o in order_by]
    if page != 1:
        payload["page"] = page
    if limit != 10:
        payload["limit"] = limit
    return payload


class Observability(SyncResource):
    """Query observability data from the BudAI app service."""

    def query(
        self,
        prompt_id: str,
        from_date: datetime,
        *,
        version: str | None = None,
        to_date: datetime | None = None,
        trace_id: str | None = None,
        span_names: list[str] | None = None,
        depth: int = 0,
        select_attributes: list[str] | None = None,
        include_all_attributes: bool = False,
        include_resource_attributes: bool = False,
        include_events: bool = False,
        include_links: bool = False,
        span_filters: list[FilterCondition] | None = None,
        resource_filters: list[FilterCondition] | None = None,
        order_by: list[OrderBySpec] | None = None,
        page: int = 1,
        limit: int = 10,
    ) -> TelemetryQueryResponse:
        """Query telemetry span data.

        Args:
            prompt_id: Prompt identifier to query spans for.
            from_date: Start of the time range.
            version: Filter by prompt version.
            to_date: End of the time range.
            trace_id: Filter to a specific trace.
            span_names: Filter by span names.
            depth: Child span depth (0 = root only).
            select_attributes: Specific attributes to include.
            include_all_attributes: Include all span attributes.
            include_resource_attributes: Include resource attributes.
            include_events: Include span events.
            include_links: Include span links.
            span_filters: Additional span filter conditions.
            resource_filters: Additional resource filter conditions.
            order_by: Sort specifications.
            page: Page number (1-based).
            limit: Results per page.

        Returns:
            TelemetryQueryResponse with span data and pagination info.
        """
        payload = _build_query_payload(
            prompt_id,
            from_date,
            version=version,
            to_date=to_date,
            trace_id=trace_id,
            span_names=span_names,
            depth=depth,
            select_attributes=select_attributes,
            include_all_attributes=include_all_attributes,
            include_resource_attributes=include_resource_attributes,
            include_events=include_events,
            include_links=include_links,
            span_filters=span_filters,
            resource_filters=resource_filters,
            order_by=order_by,
            page=page,
            limit=limit,
        )
        data = self._http.post("/prompts/telemetry/query", json=payload)
        return TelemetryQueryResponse.model_validate(data)


class AsyncObservability(AsyncResource):
    """Async observability query resource."""

    async def query(
        self,
        prompt_id: str,
        from_date: datetime,
        *,
        version: str | None = None,
        to_date: datetime | None = None,
        trace_id: str | None = None,
        span_names: list[str] | None = None,
        depth: int = 0,
        select_attributes: list[str] | None = None,
        include_all_attributes: bool = False,
        include_resource_attributes: bool = False,
        include_events: bool = False,
        include_links: bool = False,
        span_filters: list[FilterCondition] | None = None,
        resource_filters: list[FilterCondition] | None = None,
        order_by: list[OrderBySpec] | None = None,
        page: int = 1,
        limit: int = 10,
    ) -> TelemetryQueryResponse:
        """Query telemetry span data (async).

        See Observability.query for parameter documentation.
        """
        payload = _build_query_payload(
            prompt_id,
            from_date,
            version=version,
            to_date=to_date,
            trace_id=trace_id,
            span_names=span_names,
            depth=depth,
            select_attributes=select_attributes,
            include_all_attributes=include_all_attributes,
            include_resource_attributes=include_resource_attributes,
            include_events=include_events,
            include_links=include_links,
            span_filters=span_filters,
            resource_filters=resource_filters,
            order_by=order_by,
            page=page,
            limit=limit,
        )
        data = await self._http.post("/prompts/telemetry/query", json=payload)
        return TelemetryQueryResponse.model_validate(data)
