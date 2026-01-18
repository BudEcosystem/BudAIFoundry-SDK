"""Tests for Audit resource."""

from __future__ import annotations

import httpx
import respx

from bud._http import HttpClient
from bud.auth import APIKeyAuth
from bud.resources.audit import Audit


class TestAuditResource:
    """Test Audit resource methods."""

    @respx.mock
    def test_audit_list(self) -> None:
        """Audit should list audit records."""
        respx.get("https://api.example.com/audit/records").mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "audit-1",
                            "action": "pipeline.created",
                            "user_id": "user-123",
                            "timestamp": "2024-01-01T00:00:00Z",
                        },
                        {
                            "id": "audit-2",
                            "action": "execution.started",
                            "user_id": "user-123",
                            "timestamp": "2024-01-01T01:00:00Z",
                        },
                    ],
                    "total": 2,
                },
            )
        )

        auth = APIKeyAuth(api_key="test-key")
        http = HttpClient(base_url="https://api.example.com", auth=auth)
        audit = Audit(http)

        result = audit.list()

        assert len(result.items) == 2
        assert result.items[0].action == "pipeline.created"

    @respx.mock
    def test_audit_list_with_filters(self) -> None:
        """Audit should list with filters."""
        route = respx.get("https://api.example.com/audit/records").mock(
            return_value=httpx.Response(
                200,
                json={"items": [], "total": 0},
            )
        )

        auth = APIKeyAuth(api_key="test-key")
        http = HttpClient(base_url="https://api.example.com", auth=auth)
        audit = Audit(http)

        audit.list(
            user_id="user-123",
            action="pipeline.created",
            limit=10,
        )

        request = route.calls.last.request
        assert "user_id=user-123" in str(request.url)
        assert "action=pipeline.created" in str(request.url)

    @respx.mock
    def test_audit_get(self) -> None:
        """Audit should get a single record."""
        respx.get("https://api.example.com/audit/records/audit-1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "audit-1",
                    "action": "pipeline.created",
                    "user_id": "user-123",
                    "timestamp": "2024-01-01T00:00:00Z",
                    "details": {"pipeline_id": "pipe-1", "name": "My Pipeline"},
                },
            )
        )

        auth = APIKeyAuth(api_key="test-key")
        http = HttpClient(base_url="https://api.example.com", auth=auth)
        audit = Audit(http)

        result = audit.get("audit-1")

        assert result.id == "audit-1"
        assert result.action == "pipeline.created"
        assert result.details["pipeline_id"] == "pipe-1"

    @respx.mock
    def test_audit_get_summary(self) -> None:
        """Audit should get audit summary."""
        respx.get("https://api.example.com/audit/summary").mock(
            return_value=httpx.Response(
                200,
                json={
                    "total_records": 1000,
                    "actions": {
                        "pipeline.created": 100,
                        "pipeline.deleted": 20,
                        "execution.started": 500,
                    },
                    "users": {"user-123": 400, "user-456": 600},
                },
            )
        )

        auth = APIKeyAuth(api_key="test-key")
        http = HttpClient(base_url="https://api.example.com", auth=auth)
        audit = Audit(http)

        result = audit.get_summary()

        assert result["total_records"] == 1000
        assert result["actions"]["pipeline.created"] == 100

    @respx.mock
    def test_audit_verify(self) -> None:
        """Audit should verify a single record."""
        respx.get("https://api.example.com/audit/records/audit-1/verify").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "audit-1",
                    "verified": True,
                    "hash": "abc123",
                },
            )
        )

        auth = APIKeyAuth(api_key="test-key")
        http = HttpClient(base_url="https://api.example.com", auth=auth)
        audit = Audit(http)

        result = audit.verify("audit-1")

        assert result["verified"] is True
        assert result["hash"] == "abc123"

    @respx.mock
    def test_audit_verify_batch(self) -> None:
        """Audit should verify multiple records."""
        respx.post("https://api.example.com/audit/verify-batch").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": "audit-1", "verified": True},
                        {"id": "audit-2", "verified": True},
                        {"id": "audit-3", "verified": False},
                    ],
                    "total_verified": 2,
                    "total_failed": 1,
                },
            )
        )

        auth = APIKeyAuth(api_key="test-key")
        http = HttpClient(base_url="https://api.example.com", auth=auth)
        audit = Audit(http)

        result = audit.verify_batch(["audit-1", "audit-2", "audit-3"])

        assert result["total_verified"] == 2
        assert result["total_failed"] == 1

    @respx.mock
    def test_audit_find_tampered(self) -> None:
        """Audit should find tampered records."""
        respx.get("https://api.example.com/audit/find-tampered").mock(
            return_value=httpx.Response(
                200,
                json={
                    "tampered_records": [
                        {"id": "audit-bad-1", "issue": "hash_mismatch"},
                    ],
                    "total": 1,
                },
            )
        )

        auth = APIKeyAuth(api_key="test-key")
        http = HttpClient(base_url="https://api.example.com", auth=auth)
        audit = Audit(http)

        result = audit.find_tampered()

        assert len(result["tampered_records"]) == 1
        assert result["tampered_records"][0]["issue"] == "hash_mismatch"
