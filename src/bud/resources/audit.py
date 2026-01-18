"""Audit resource for BudAI SDK."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from bud.models.audit import AuditList, AuditRecord
from bud.resources._base import SyncResource

if TYPE_CHECKING:
    from bud._http import HttpClient


class Audit(SyncResource):
    """Audit resource for viewing and verifying audit records.

    Example:
        ```python
        from bud import BudClient

        client = BudClient(api_key="your-key")

        # List audit records
        records = client.audit.list(action="pipeline.created")
        for record in records.items:
            print(f"{record.action}: {record.timestamp}")

        # Get a specific record
        record = client.audit.get("audit-id")

        # Verify record integrity
        result = client.audit.verify("audit-id")
        print(f"Verified: {result['verified']}")
        ```
    """

    def __init__(self, http: HttpClient) -> None:
        """Initialize audit resource.

        Args:
            http: HTTP client instance.
        """
        super().__init__(http)

    def list(
        self,
        *,
        user_id: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> AuditList:
        """List audit records.

        Args:
            user_id: Filter by user ID.
            action: Filter by action type.
            resource_type: Filter by resource type.
            resource_id: Filter by resource ID.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            AuditList with items and pagination.
        """
        params = {}
        if user_id:
            params["user_id"] = user_id
        if action:
            params["action"] = action
        if resource_type:
            params["resource_type"] = resource_type
        if resource_id:
            params["resource_id"] = resource_id
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset

        data = self._http.get("/audit/records", params=params)
        return AuditList.model_validate(data)

    def get(self, record_id: str) -> AuditRecord:
        """Get a specific audit record.

        Args:
            record_id: The audit record ID.

        Returns:
            AuditRecord details.
        """
        data = self._http.get(f"/audit/records/{record_id}")
        return AuditRecord.model_validate(data)

    def get_summary(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """Get audit summary statistics.

        Args:
            start_date: Start date for summary (ISO format).
            end_date: End date for summary (ISO format).

        Returns:
            Summary dictionary with statistics.
        """
        params = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        return self._http.get("/audit/summary", params=params)

    def verify(self, record_id: str) -> dict[str, Any]:
        """Verify integrity of an audit record.

        Args:
            record_id: The audit record ID to verify.

        Returns:
            Verification result with 'verified' boolean and details.
        """
        return self._http.get(f"/audit/records/{record_id}/verify")

    def verify_batch(self, record_ids: list[str]) -> dict[str, Any]:
        """Verify integrity of multiple audit records.

        Args:
            record_ids: List of record IDs to verify.

        Returns:
            Batch verification results.
        """
        return self._http.post("/audit/verify-batch", json={"ids": record_ids})

    def find_tampered(self) -> dict[str, Any]:
        """Find potentially tampered audit records.

        Returns:
            Dictionary with tampered records and anomalies.
        """
        return self._http.get("/audit/find-tampered")


class AsyncAudit:
    """Async audit resource for viewing and verifying audit records."""

    def __init__(self, http) -> None:
        """Initialize async audit resource.

        Args:
            http: Async HTTP client instance.
        """
        self._http = http

    async def list(
        self,
        *,
        user_id: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> AuditList:
        """List audit records."""
        params = {}
        if user_id:
            params["user_id"] = user_id
        if action:
            params["action"] = action
        if resource_type:
            params["resource_type"] = resource_type
        if resource_id:
            params["resource_id"] = resource_id
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset

        data = await self._http.get("/audit/records", params=params)
        return AuditList.model_validate(data)

    async def get(self, record_id: str) -> AuditRecord:
        """Get a specific audit record."""
        data = await self._http.get(f"/audit/records/{record_id}")
        return AuditRecord.model_validate(data)

    async def get_summary(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """Get audit summary statistics."""
        params = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        return await self._http.get("/audit/summary", params=params)

    async def verify(self, record_id: str) -> dict[str, Any]:
        """Verify integrity of an audit record."""
        return await self._http.get(f"/audit/records/{record_id}/verify")

    async def verify_batch(self, record_ids: list[str]) -> dict[str, Any]:
        """Verify integrity of multiple audit records."""
        return await self._http.post("/audit/verify-batch", json={"ids": record_ids})

    async def find_tampered(self) -> dict[str, Any]:
        """Find potentially tampered audit records."""
        return await self._http.get("/audit/find-tampered")
