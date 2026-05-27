"""Agent (= prompt-version) operations for the BudAI Foundry SDK.

Thin wrapper over budapp's existing prompt-native-tool endpoints:

* ``POST   /prompts/{agent_id}/native-tools``
* ``GET    /prompts/{agent_id}/native-tools/{tool_name}``
* ``DELETE /prompts/{agent_id}/native-tools/{tool_name}``

These endpoints accept both JWT (UI session) and project api-key auth via
budapp's hybrid auth dep — the SDK uses the api-key path. There is no new
"agents" backend; the routes are reused, the SDK just gives them an
ergonomic surface.

v1 only exposes ``code_interpreter`` attach / get / detach. Other native
tools (``web_search`` / ``web_fetch``) are UI-only until a user asks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from bud.exceptions import NotFoundError
from bud.models.code_interpreter import AgentToolBinding, NetworkPolicy
from bud.resources._base import AsyncResource, SyncResource

if TYPE_CHECKING:
    pass


_TOOL_NAME = "code_interpreter"


def _native_tools_path(agent_id: str) -> str:
    return f"/prompts/{agent_id}/native-tools"


def _native_tool_path(agent_id: str, tool_name: str = _TOOL_NAME) -> str:
    return f"/prompts/{agent_id}/native-tools/{tool_name}"


def _coerce_network_policy(policy: NetworkPolicy | dict | None) -> dict | None:
    """Accept either a :class:`NetworkPolicy` model or a raw dict."""
    if policy is None:
        return None
    if isinstance(policy, NetworkPolicy):
        return policy.model_dump()
    return dict(policy)


def _build_upsert_body(
    *,
    template_id: str,
    version: int,
    lifespan_seconds: int,
    network_policy: NetworkPolicy | dict | None,
) -> dict:
    """Assemble the ``POST /prompts/{id}/native-tools`` body for code_interpreter.

    Backend's ``CodeInterpreterConfigInput`` accepts
    ``custom_template_id`` as a sibling of ``cpu`` / ``ram_gb``; the SDK
    always uses the custom-template path because builtin selection happens
    via cpu/ram in the UI, not via the SDK.

    ``permanent`` is pinned to ``True`` so calls against permanent prompts
    don't get rejected by budapp as a downgrade.
    """
    config: dict[str, Any] = {
        "custom_template_id": template_id,
        "container_expiry_seconds": lifespan_seconds,
    }
    resolved_policy = _coerce_network_policy(network_policy)
    if resolved_policy is not None:
        config["network_policy"] = resolved_policy
    return {
        "tool_name": _TOOL_NAME,
        "config": config,
        "version": version,
        "permanent": True,
    }


def _extract_binding(
    payload: object,
    *,
    agent_id: str,
    fallback_version: int,
) -> AgentToolBinding:
    """Build an :class:`AgentToolBinding` from a budapp envelope.

    budapp returns ``{"tool": {"name": ..., "connected_config": {...}}}`` on
    upsert and ``{"tool": {"name": ..., "connected_config": {...}}}`` on get.
    The ``env_id`` lives inside ``connected_config``.
    """
    tool: dict[str, Any] = {}
    if isinstance(payload, dict):
        if isinstance(payload.get("tool"), dict):
            tool = payload["tool"]
        else:
            tool = payload
    connected_config = tool.get("connected_config") or {}
    env_id = connected_config.get("env_id") or ""
    custom_template_id = connected_config.get("custom_template_id")
    template_id = custom_template_id or connected_config.get("template_id")
    version = connected_config.get("version") or fallback_version or 1
    return AgentToolBinding(
        agent_id=agent_id,
        version=int(version),
        tool_name=_TOOL_NAME,
        env_id=env_id,
        template_id=template_id,
        custom_template_id=custom_template_id,
        config=connected_config or None,
    )


# ---------------------------------------------------------------------------
# Sync surface
# ---------------------------------------------------------------------------


class Agents(SyncResource):
    """Sync agent operations (code_interpreter attach / get / detach)."""

    def add_code_interpreter(
        self,
        agent_id: str,
        *,
        template_id: str,
        version: int = 1,
        lifespan_seconds: int = 1200,
        network_policy: NetworkPolicy | dict | None = None,
    ) -> AgentToolBinding:
        """Attach (or update) the code-interpreter tool on an agent version.

        Args:
            agent_id: The agent (prompt) id.
            template_id: A builtin (``"python-4g"``) or a custom template
                id returned by :meth:`Templates.create`.
            version: Agent version number. Defaults to 1.
            lifespan_seconds: Sandbox idle-kill timeout. Default 1200s.
            network_policy: Egress policy (``NetworkPolicy`` or raw dict).

        Returns:
            The bound :class:`AgentToolBinding` — ``env_id`` is the
            auto-provisioned budcodeinterpreter env id (read-only).

        Raises:
            NotFoundError: Agent or template not found / cross-project.
            ValidationError: Config rejected by the schema validator.
        """
        body = _build_upsert_body(
            template_id=template_id,
            version=version,
            lifespan_seconds=lifespan_seconds,
            network_policy=network_policy,
        )
        payload = self._http.post(_native_tools_path(agent_id), json=body)
        return _extract_binding(payload, agent_id=agent_id, fallback_version=version)

    def get_code_interpreter(
        self,
        agent_id: str,
        version: int = 1,
    ) -> AgentToolBinding | None:
        """Fetch the agent's current code-interpreter binding (or ``None``).

        Args:
            agent_id: The agent (prompt) id.
            version: Agent version number. Defaults to 1.
        """
        try:
            payload = self._http.get(_native_tool_path(agent_id), params={"version": version})
        except NotFoundError:
            return None
        binding = _extract_binding(payload, agent_id=agent_id, fallback_version=version)
        # An "unconnected" detail response still returns 200; treat empty env_id
        # as "no binding present" for caller convenience.
        if not binding.env_id:
            return None
        return binding

    def remove_code_interpreter(
        self,
        agent_id: str,
        version: int = 1,
    ) -> None:
        """Detach the code-interpreter tool. Idempotent — 404 is a no-op.

        Args:
            agent_id: The agent (prompt) id.
            version: Agent version number. Defaults to 1.
        """
        try:
            self._http.delete(
                _native_tool_path(agent_id),
                params={"version": version, "permanent": True},
            )
        except NotFoundError:
            return


# ---------------------------------------------------------------------------
# Async surface
# ---------------------------------------------------------------------------


class AsyncAgents(AsyncResource):
    """Async agent operations (code_interpreter attach / get / detach)."""

    async def add_code_interpreter(
        self,
        agent_id: str,
        *,
        template_id: str,
        version: int = 1,
        lifespan_seconds: int = 1200,
        network_policy: NetworkPolicy | dict | None = None,
    ) -> AgentToolBinding:
        """Async equivalent of :meth:`Agents.add_code_interpreter`."""
        body = _build_upsert_body(
            template_id=template_id,
            version=version,
            lifespan_seconds=lifespan_seconds,
            network_policy=network_policy,
        )
        payload = await self._http.post(_native_tools_path(agent_id), json=body)
        return _extract_binding(payload, agent_id=agent_id, fallback_version=version)

    async def get_code_interpreter(
        self,
        agent_id: str,
        version: int = 1,
    ) -> AgentToolBinding | None:
        """Async equivalent of :meth:`Agents.get_code_interpreter`."""
        try:
            payload = await self._http.get(_native_tool_path(agent_id), params={"version": version})
        except NotFoundError:
            return None
        binding = _extract_binding(payload, agent_id=agent_id, fallback_version=version)
        if not binding.env_id:
            return None
        return binding

    async def remove_code_interpreter(
        self,
        agent_id: str,
        version: int = 1,
    ) -> None:
        """Async equivalent of :meth:`Agents.remove_code_interpreter`."""
        try:
            await self._http.delete(
                _native_tool_path(agent_id),
                params={"version": version, "permanent": True},
            )
        except NotFoundError:
            return


__all__ = ["Agents", "AsyncAgents"]
