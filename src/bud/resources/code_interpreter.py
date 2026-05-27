"""Code-interpreter custom-template resources.

Backed by budapp's ``/prompts/code-interpreter/templates/*`` endpoints. The
SDK is a thin wrapper — all Dockerfile-instruction validation, alias
derivation, and sandbox build orchestration happen server-side.

Exposed via ``client.code_interpreter.templates`` on both :class:`BudClient`
and :class:`AsyncBudClient`. The returned :class:`Template` object carries
a ``.refresh()`` / ``.wait_until_ready()`` helper pair so callers can poll
for build completion without managing the HTTP layer themselves.

``templates.create()`` and ``templates.update()`` schedule a Dapr workflow
on the backend and return immediately with a partial ``Template`` whose
``status='pending'`` until Activity 1 of the workflow runs (~50–500 ms
after the route returns). ``.refresh()`` / ``.wait_until_ready()`` are
tolerant of 404s during a short grace window so the race between the
schedule response and the row insert doesn't surface as an error.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from bud.exceptions import BuildFailedError, NotFoundError
from bud.models.code_interpreter import Template
from bud.resources._base import AsyncResource, SyncResource

if TYPE_CHECKING:
    from bud._http import AsyncHttpClient, HttpClient


_TEMPLATES_PATH = "/prompts/code-interpreter/templates"

# Grace window after a workflow-scheduling create / update during which a
# 404 from GET ``/templates/{id}`` is treated as "row not yet inserted by
# Activity 1" rather than a real not-found. After this window elapses,
# 404s propagate as :class:`NotFoundError`.
_CREATE_GRACE_SECONDS: float = 10.0


def _template_path(template_id: str) -> str:
    return f"{_TEMPLATES_PATH}/{template_id}"


def _extract_template(payload: object) -> dict:
    """Pull the ``template`` block from a budapp envelope (or pass through)."""
    if isinstance(payload, dict) and "template" in payload:
        return payload["template"] or {}
    return payload if isinstance(payload, dict) else {}


def _make_pending_template_dict(
    *,
    name: str,
    commands: list[str],
    cpu_count: int,
    memory_mb: int,
    scheduled: object,
) -> dict:
    """Build the partial ``Template`` dict returned by create / update.

    The scheduled response from budapp carries ``workflow_id`` /
    ``template_id`` / ``status='pending'``; the SDK doesn't see the
    inserted row yet (race window — see module docstring). Backfill the
    fields the user just supplied so the returned ``Template`` looks
    coherent until the first ``.refresh()`` succeeds.
    """
    scheduled_dict = scheduled if isinstance(scheduled, dict) else {}
    template_id = scheduled_dict.get("template_id") or name
    return {
        "id": template_id,
        "type": "custom",
        "status": scheduled_dict.get("status") or "pending",
        "commands": list(commands),
        "languages": ["python", "javascript"],
        "cpu_count": cpu_count,
        "memory_mb": memory_mb,
    }


# ---------------------------------------------------------------------------
# Sync surface
# ---------------------------------------------------------------------------


class _SyncTemplateHandle(Template):
    """Sync ``Template`` with ``.refresh()`` / ``.wait_until_ready()``."""

    def _bind(self, http: HttpClient, *, grace_window: float = 0.0) -> _SyncTemplateHandle:
        # Attach the http client without making it a pydantic field — avoids
        # serialising the client when the model is dumped to JSON.
        object.__setattr__(self, "_http_client", http)
        object.__setattr__(
            self, "_grace_deadline", time.monotonic() + grace_window if grace_window > 0 else 0.0
        )
        return self

    def refresh(self) -> _SyncTemplateHandle:
        """Re-fetch the row from the server; mutate self in place.

        Returns ``self`` so callers can chain (``tpl.refresh().status``).

        Tolerates 404 for the configured grace window after create / update
        — the row may not exist yet because Activity 1 of the create /
        update workflow hasn't run. After the grace elapses, 404 becomes
        a real :class:`NotFoundError`.
        """
        http = getattr(self, "_http_client", None)
        if http is None:  # pragma: no cover — defensive only
            raise RuntimeError("Template handle is not bound to an HTTP client")
        try:
            payload = http.get(_template_path(self.id))
        except NotFoundError:
            grace_deadline = getattr(self, "_grace_deadline", 0.0)
            if time.monotonic() < grace_deadline:
                return self  # still within race window — keep current pending state
            raise
        fresh = Template.model_validate(_extract_template(payload))
        for field in fresh.model_fields:
            object.__setattr__(self, field, getattr(fresh, field))
        return self

    def wait_until_ready(
        self,
        *,
        timeout: float = 600.0,
        poll_interval: float = 3.0,
    ) -> _SyncTemplateHandle:
        """Block until status flips to ``ready`` or raise on failure.

        Args:
            timeout: Total seconds to wait before raising :class:`TimeoutError`.
            poll_interval: Seconds between successive ``refresh()`` calls.

        Returns:
            ``self`` once status reaches ``ready``.

        Raises:
            BuildFailedError: Server reported ``status='failed'`` — the
                captured stderr tail is on ``error_message``.
            TimeoutError: ``timeout`` elapsed with status still ``building``.
        """
        deadline = time.monotonic() + timeout
        while True:
            self.refresh()
            if self.status == "ready":
                return self
            if self.status == "failed":
                raise BuildFailedError(
                    f"Template build failed: {self.error_message or '(no error message)'}",
                    template_id=self.id,
                    error_message=self.error_message,
                )
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Template {self.id!r} did not reach 'ready' within {timeout}s "
                    f"(last status={self.status!r})"
                )
            time.sleep(poll_interval)


class Templates(SyncResource):
    """Sync code-interpreter custom-template operations."""

    def create(
        self,
        *,
        name: str,
        commands: list[str],
        cpu_count: int,
        memory_mb: int,
    ) -> _SyncTemplateHandle:
        """Schedule the create-template workflow on the backend.

        Returns immediately with a partial ``Template`` (``status='pending'``).
        Call ``.wait_until_ready()`` to block until the workflow inserts the
        row, runs the build, and finalises the status.

        Args:
            name: Slug-safe template name (also the template id).
            commands: Dockerfile-instruction strings appended to the shared
                base. Server enforces the deny-list (no ``FROM`` / ``COPY``
                / ``ADD`` / ``CMD`` / ``ENTRYPOINT``) and a typo catcher.
            cpu_count: vCPU count.
            memory_mb: Memory in MiB.

        Returns:
            A ``Template`` handle with ``status='pending'``. A short grace
            window (default 10 s) absorbs 404s from the first ``refresh()``
            calls while the workflow's insert activity catches up.

        Raises:
            ValidationError: Commands failed the server-side validator.
            ConnectionError / TimeoutError: Transport failure.
        """
        body = {
            "name": name,
            "commands": commands,
            "cpu_count": cpu_count,
            "memory_mb": memory_mb,
        }
        scheduled = self._http.post(_TEMPLATES_PATH, json=body)
        template = Template.model_validate(
            _make_pending_template_dict(
                name=name,
                commands=commands,
                cpu_count=cpu_count,
                memory_mb=memory_mb,
                scheduled=scheduled,
            )
        )
        return _SyncTemplateHandle.model_validate(template.model_dump())._bind(
            self._http, grace_window=_CREATE_GRACE_SECONDS
        )

    def get(self, template_id: str) -> _SyncTemplateHandle:
        """Fetch a single template (builtin or custom). 404 → NotFoundError."""
        payload = self._http.get(_template_path(template_id))
        template = Template.model_validate(_extract_template(payload))
        return _SyncTemplateHandle.model_validate(template.model_dump())._bind(self._http)

    def update(
        self,
        template_id: str,
        *,
        commands: list[str],
    ) -> _SyncTemplateHandle:
        """Schedule the update-template workflow (replace commands + rebuild).

        Returns immediately with a partial ``Template`` (``status='pending'``).
        The same sandbox image is rebuilt — running sandboxes keep their
        old image snapshot; the next sandbox spawn picks up the new image.

        Raises:
            NotFoundError: Cross-project / unknown template id.
            ValidationError: Commands failed the server-side validator.
        """
        body = {"commands": commands}
        scheduled = self._http.put(_template_path(template_id), json=body)
        scheduled_dict = scheduled if isinstance(scheduled, dict) else {}
        # We don't know cpu/memory ahead of time for updates — fetch them from
        # the response if present, otherwise leave defaults; .refresh() fills
        # them in once the row catches up.
        template = Template.model_validate(
            {
                "id": scheduled_dict.get("template_id") or template_id,
                "type": "custom",
                "status": scheduled_dict.get("status") or "pending",
                "commands": list(commands),
                "languages": ["python", "javascript"],
                "cpu_count": 0,
                "memory_mb": 0,
            }
        )
        return _SyncTemplateHandle.model_validate(template.model_dump())._bind(
            self._http, grace_window=_CREATE_GRACE_SECONDS
        )

    def delete(self, template_id: str) -> None:
        """Hard-delete the template row and its sandbox image.

        Idempotent — a 404 is absorbed silently. Raises ``ClientException``
        with 409 when the template is still bound to an environment.
        """
        try:
            self._http.delete(_template_path(template_id))
        except NotFoundError:
            return


# ---------------------------------------------------------------------------
# Async surface
# ---------------------------------------------------------------------------


class _AsyncTemplateHandle(Template):
    """Async ``Template`` with ``.refresh()`` / ``.wait_until_ready()``."""

    def _bind(self, http: AsyncHttpClient, *, grace_window: float = 0.0) -> _AsyncTemplateHandle:
        object.__setattr__(self, "_http_client", http)
        try:
            now = asyncio.get_running_loop().time()
        except RuntimeError:
            now = time.monotonic()
        object.__setattr__(self, "_grace_deadline", now + grace_window if grace_window > 0 else 0.0)
        return self

    async def refresh(self) -> _AsyncTemplateHandle:
        """Re-fetch the row; mutate self in place; return ``self``.

        Tolerates 404 during the create / update grace window — see the
        sync handle for the full explanation.
        """
        http = getattr(self, "_http_client", None)
        if http is None:  # pragma: no cover
            raise RuntimeError("Template handle is not bound to an HTTP client")
        try:
            payload = await http.get(_template_path(self.id))
        except NotFoundError:
            grace_deadline = getattr(self, "_grace_deadline", 0.0)
            try:
                now = asyncio.get_running_loop().time()
            except RuntimeError:
                now = time.monotonic()
            if now < grace_deadline:
                return self
            raise
        fresh = Template.model_validate(_extract_template(payload))
        for field in fresh.model_fields:
            object.__setattr__(self, field, getattr(fresh, field))
        return self

    async def wait_until_ready(
        self,
        *,
        timeout: float = 600.0,
        poll_interval: float = 3.0,
    ) -> _AsyncTemplateHandle:
        """Async block until status reaches ``ready`` or raise on failure."""
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            await self.refresh()
            if self.status == "ready":
                return self
            if self.status == "failed":
                raise BuildFailedError(
                    f"Template build failed: {self.error_message or '(no error message)'}",
                    template_id=self.id,
                    error_message=self.error_message,
                )
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError(
                    f"Template {self.id!r} did not reach 'ready' within {timeout}s "
                    f"(last status={self.status!r})"
                )
            await asyncio.sleep(poll_interval)


class AsyncTemplates(AsyncResource):
    """Async code-interpreter custom-template operations."""

    async def create(
        self,
        *,
        name: str,
        commands: list[str],
        cpu_count: int,
        memory_mb: int,
    ) -> _AsyncTemplateHandle:
        """Async equivalent of :meth:`Templates.create`."""
        body = {
            "name": name,
            "commands": commands,
            "cpu_count": cpu_count,
            "memory_mb": memory_mb,
        }
        scheduled = await self._http.post(_TEMPLATES_PATH, json=body)
        template = Template.model_validate(
            _make_pending_template_dict(
                name=name,
                commands=commands,
                cpu_count=cpu_count,
                memory_mb=memory_mb,
                scheduled=scheduled,
            )
        )
        return _AsyncTemplateHandle.model_validate(template.model_dump())._bind(
            self._http, grace_window=_CREATE_GRACE_SECONDS
        )

    async def get(self, template_id: str) -> _AsyncTemplateHandle:
        """Async equivalent of :meth:`Templates.get`."""
        payload = await self._http.get(_template_path(template_id))
        template = Template.model_validate(_extract_template(payload))
        return _AsyncTemplateHandle.model_validate(template.model_dump())._bind(self._http)

    async def update(
        self,
        template_id: str,
        *,
        commands: list[str],
    ) -> _AsyncTemplateHandle:
        """Async equivalent of :meth:`Templates.update`."""
        body = {"commands": commands}
        scheduled = await self._http.put(_template_path(template_id), json=body)
        scheduled_dict = scheduled if isinstance(scheduled, dict) else {}
        template = Template.model_validate(
            {
                "id": scheduled_dict.get("template_id") or template_id,
                "type": "custom",
                "status": scheduled_dict.get("status") or "pending",
                "commands": list(commands),
                "languages": ["python", "javascript"],
                "cpu_count": 0,
                "memory_mb": 0,
            }
        )
        return _AsyncTemplateHandle.model_validate(template.model_dump())._bind(
            self._http, grace_window=_CREATE_GRACE_SECONDS
        )

    async def delete(self, template_id: str) -> None:
        """Async equivalent of :meth:`Templates.delete`."""
        try:
            await self._http.delete(_template_path(template_id))
        except NotFoundError:
            return


# ---------------------------------------------------------------------------
# Namespace wrapper attached to the client (``client.code_interpreter``)
# ---------------------------------------------------------------------------


class CodeInterpreter:
    """Namespace exposing ``.templates`` under ``client.code_interpreter``."""

    def __init__(self, http: HttpClient) -> None:
        self.templates = Templates(http)


class AsyncCodeInterpreter:
    """Async namespace exposing ``.templates`` under ``client.code_interpreter``."""

    def __init__(self, http: AsyncHttpClient) -> None:
        self.templates = AsyncTemplates(http)


__all__ = [
    "CodeInterpreter",
    "AsyncCodeInterpreter",
    "Templates",
    "AsyncTemplates",
]
