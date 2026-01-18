"""Webhook resource operations."""

from __future__ import annotations

from typing import Any

from bud.models.webhook import Webhook, WebhookSecret, WebhookTriggerResult
from bud.resources._base import AsyncResource, SyncResource


class Webhooks(SyncResource):
    """Webhook operations."""

    def create(
        self,
        pipeline_id: str,
        *,
        name: str,
        description: str = "",
        headers: dict[str, str] | None = None,
    ) -> WebhookSecret:
        """Create a new webhook.

        Args:
            pipeline_id: Pipeline ID
            name: Webhook name
            description: Webhook description
            headers: Expected headers for validation

        Returns:
            Webhook with secret (secret only shown once)
        """
        data = self._http.post(
            "/budpipeline/webhooks",
            json={
                "pipeline_id": pipeline_id,
                "name": name,
                "description": description,
                "headers": headers or {},
            },
        )
        return WebhookSecret.model_validate(data)

    def list(
        self,
        *,
        pipeline_id: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> list[Webhook]:
        """List webhooks.

        Args:
            pipeline_id: Filter by pipeline ID
            page: Page number
            per_page: Items per page

        Returns:
            List of webhooks
        """
        params: dict[str, Any] = {
            "page": page,
            "per_page": per_page,
        }
        if pipeline_id:
            params["pipeline_id"] = pipeline_id

        data = self._http.get("/budpipeline/webhooks", params=params)
        items = data.get("items", data) if isinstance(data, dict) else data
        return [Webhook.model_validate(item) for item in items]

    def get(self, webhook_id: str) -> Webhook:
        """Get a webhook by ID.

        Args:
            webhook_id: Webhook ID

        Returns:
            Webhook
        """
        data = self._http.get(f"/budpipeline/webhooks/{webhook_id}")
        return Webhook.model_validate(data)

    def delete(self, webhook_id: str) -> None:
        """Delete a webhook.

        Args:
            webhook_id: Webhook ID
        """
        self._http.delete(f"/budpipeline/webhooks/{webhook_id}")

    def rotate_secret(self, webhook_id: str) -> WebhookSecret:
        """Rotate webhook secret.

        Args:
            webhook_id: Webhook ID

        Returns:
            New webhook secret
        """
        data = self._http.post(f"/budpipeline/webhooks/{webhook_id}/rotate-secret", json={})
        return WebhookSecret.model_validate(data)

    def trigger(
        self,
        webhook_id: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> WebhookTriggerResult:
        """Trigger a webhook (for testing).

        Args:
            webhook_id: Webhook ID
            payload: Webhook payload

        Returns:
            Trigger result with execution ID
        """
        data = self._http.post(
            f"/budpipeline/webhooks/{webhook_id}/trigger",
            json={"payload": payload or {}},
        )
        return WebhookTriggerResult.model_validate(data)


class AsyncWebhooks(AsyncResource):
    """Async webhook operations."""

    async def create(
        self,
        pipeline_id: str,
        *,
        name: str,
        description: str = "",
        headers: dict[str, str] | None = None,
    ) -> WebhookSecret:
        """Create a new webhook."""
        data = await self._http.post(
            "/budpipeline/webhooks",
            json={
                "pipeline_id": pipeline_id,
                "name": name,
                "description": description,
                "headers": headers or {},
            },
        )
        return WebhookSecret.model_validate(data)

    async def list(
        self,
        *,
        pipeline_id: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> list[Webhook]:
        """List webhooks."""
        params: dict[str, Any] = {
            "page": page,
            "per_page": per_page,
        }
        if pipeline_id:
            params["pipeline_id"] = pipeline_id

        data = await self._http.get("/budpipeline/webhooks", params=params)
        items = data.get("items", data) if isinstance(data, dict) else data
        return [Webhook.model_validate(item) for item in items]

    async def get(self, webhook_id: str) -> Webhook:
        """Get a webhook by ID."""
        data = await self._http.get(f"/budpipeline/webhooks/{webhook_id}")
        return Webhook.model_validate(data)

    async def delete(self, webhook_id: str) -> None:
        """Delete a webhook."""
        await self._http.delete(f"/budpipeline/webhooks/{webhook_id}")

    async def rotate_secret(self, webhook_id: str) -> WebhookSecret:
        """Rotate webhook secret."""
        data = await self._http.post(f"/budpipeline/webhooks/{webhook_id}/rotate-secret", json={})
        return WebhookSecret.model_validate(data)

    async def trigger(
        self,
        webhook_id: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> WebhookTriggerResult:
        """Trigger a webhook (for testing)."""
        data = await self._http.post(
            f"/budpipeline/webhooks/{webhook_id}/trigger",
            json={"payload": payload or {}},
        )
        return WebhookTriggerResult.model_validate(data)
